"""
Retention lifecycle: state transitions, the four completion signals, hold
enforcement, ledger integrity and post-erasure verification.
"""

from __future__ import annotations

import json
import time

import pytest

from tools import retention as rt

DAY = 86400.0


@pytest.fixture
def store(tmp_path):
    records: list[dict] = []

    def load():
        return records

    def save(new):
        records[:] = new

    workspaces: dict[str, str] = {}

    s = rt.RetentionStore(
        load_records=load,
        save_records=save,
        archive_dir=tmp_path / "archive",
        ledger=rt.AuditLedger(tmp_path / "audit.jsonl"),
        live_sessions={},
        workspace_for=lambda sid: workspaces.get(sid, ""),
    )
    s._records = records          # test handle
    s._workspaces = workspaces    # test handle
    return s


def make_record(scan_id="abc123", age_days=0.0, findings=3):
    ts = time.time() - age_days * DAY
    return {
        "scan_id": scan_id,
        "lifecycle": rt.default_lifecycle(ts),
        "domain": "example.com",
        "repo_url": "https://example.com",
        "scan_date": time.strftime("%Y-%m-%d", time.gmtime(ts)),
        "timestamp": ts,
        "total_vulns": findings,
        "severity": {"critical": 0, "high": 1, "medium": 1, "low": 1},
        "risk_score": 42,
        "overall_risk": "MEDIUM",
        "vulnerabilities": [{"id": f"VULN-{i:03d}", "severity": "LOW"} for i in range(findings)],
        "patches": [{"file": "a.py"}],
        "summary": {"risk_score": 42, "executive_summary": "text"},
    }


def outcomes(receipt):
    return {c.component: c.outcome for c in receipt.components}


# ── archive ───────────────────────────────────────────────────

def test_archive_moves_payload_to_cold_storage_and_reports_complete(store):
    store._records.append(make_record())

    receipt = store.archive("abc123")

    assert receipt.outcome == rt.OUTCOME_COMPLETE
    assert receipt.state == rt.STATE_ARCHIVED
    record = store._records[0]
    assert "vulnerabilities" not in record
    assert record["risk_score"] == 42          # summary row stays hot
    cold = store._archive_path("abc123")
    assert cold.exists()
    assert len(json.loads(cold.read_text())["vulnerabilities"]) == 3


def test_restore_rehydrates_the_payload_and_verifies_its_hash(store):
    store._records.append(make_record())
    store.archive("abc123")

    receipt = store.restore("abc123")

    assert receipt.outcome == rt.OUTCOME_COMPLETE
    assert receipt.state == rt.STATE_ACTIVE
    assert len(store._records[0]["vulnerabilities"]) == 3
    assert not store._archive_path("abc123").exists()


def test_restore_flags_a_tampered_cold_copy_as_unresolved(store):
    store._records.append(make_record())
    store.archive("abc123")
    cold = store._archive_path("abc123")
    payload = json.loads(cold.read_text())
    payload["vulnerabilities"].pop()
    cold.write_text(json.dumps(payload))

    receipt = store.restore("abc123")

    assert receipt.outcome == rt.OUTCOME_UNRESOLVED
    assert outcomes(receipt)["report_payload"] == rt.C_UNRESOLVED


def test_restore_of_a_missing_cold_copy_is_unresolved_not_silent(store):
    store._records.append(make_record())
    store.archive("abc123")
    store._archive_path("abc123").unlink()

    receipt = store.restore("abc123")

    assert receipt.outcome == rt.OUTCOME_UNRESOLVED
    assert receipt.state == rt.STATE_ARCHIVED     # state is not advanced on a failure


# ── trash ─────────────────────────────────────────────────────

def test_trash_is_partial_because_the_data_is_still_recoverable(store):
    store._records.append(make_record())

    receipt = store.trash("abc123")

    assert receipt.outcome == rt.OUTCOME_PARTIAL
    assert receipt.state == rt.STATE_TRASHED
    assert outcomes(receipt)["report_payload"] == rt.C_RETAINED
    assert store._records[0]["vulnerabilities"]      # nothing was destroyed


def test_restore_takes_a_scan_back_out_of_the_trash(store):
    store._records.append(make_record())
    store.trash("abc123")

    receipt = store.restore("abc123")

    assert receipt.outcome == rt.OUTCOME_COMPLETE
    assert store._records[0]["lifecycle"]["state"] == rt.STATE_ACTIVE


# ── purge ─────────────────────────────────────────────────────

def test_full_purge_is_complete_and_leaves_only_a_tombstone(store):
    store._records.append(make_record())

    receipt = store.purge("abc123", mode=rt.PURGE_FULL)

    assert receipt.outcome == rt.OUTCOME_COMPLETE
    assert store._records == []
    assert receipt.tombstone["findings_erased"] == 3
    assert len(receipt.tombstone["payload_sha256"]) == 64
    assert outcomes(receipt)["audit_tombstone"] == rt.C_POLICY


def test_payload_purge_is_partial_and_keeps_the_score_row(store):
    store._records.append(make_record())

    receipt = store.purge("abc123", mode=rt.PURGE_PAYLOAD)

    assert receipt.outcome == rt.OUTCOME_PARTIAL
    record = store._records[0]
    assert record["risk_score"] == 42
    assert "vulnerabilities" not in record
    assert "summary" not in record
    assert record["lifecycle"]["state"] == rt.STATE_PURGED


def test_purge_also_clears_the_cold_copy_and_the_clone_workspace(store, tmp_path):
    workspace = tmp_path / "clone_abc123"
    workspace.mkdir()
    (workspace / "file.py").write_text("secret")
    store._workspaces["abc123"] = str(workspace)
    store._records.append(make_record())
    store.archive("abc123")
    # archiving already removes the workspace, so put it back to prove purge does too
    workspace.mkdir(exist_ok=True)

    receipt = store.purge("abc123", mode=rt.PURGE_FULL)

    assert outcomes(receipt)["archive_copy"] == rt.C_DONE
    assert outcomes(receipt)["clone_workspace"] == rt.C_DONE
    assert not workspace.exists()
    assert not store._archive_path("abc123").exists()


def test_purged_data_cannot_be_restored(store):
    store._records.append(make_record())
    store.purge("abc123", mode=rt.PURGE_PAYLOAD)

    receipt = store.restore("abc123")

    assert receipt.outcome == rt.OUTCOME_UNRESOLVED


def test_unknown_purge_mode_is_rejected(store):
    store._records.append(make_record())
    with pytest.raises(rt.RetentionError):
        store.purge("abc123", mode="shred")


# ── holds ─────────────────────────────────────────────────────

@pytest.mark.parametrize("operation", ["archive", "trash", "purge"])
def test_a_hold_blocks_every_destructive_operation(store, operation):
    store._records.append(make_record())
    store.place_hold("abc123", "Incident INC-4412 under investigation")

    receipt = getattr(store, operation)("abc123")

    assert receipt.outcome == rt.OUTCOME_BLOCKED
    assert "INC-4412" in receipt.components[0].detail
    assert store._records[0]["vulnerabilities"]          # untouched
    assert store._records[0]["lifecycle"]["state"] == rt.STATE_ACTIVE


def test_releasing_the_hold_lets_the_operation_through(store):
    store._records.append(make_record())
    store.place_hold("abc123", "hold")
    store.release_hold("abc123")

    assert store.trash("abc123").outcome == rt.OUTCOME_PARTIAL


def test_a_running_scan_blocks_deletion(store):
    store._records.append(make_record())
    store.live_sessions["abc123"] = {"status": "scanning"}

    receipt = store.trash("abc123")

    assert receipt.outcome == rt.OUTCOME_BLOCKED
    assert "still running" in receipt.components[0].detail


def test_a_finished_scan_in_memory_does_not_block_deletion(store):
    store._records.append(make_record())
    store.live_sessions["abc123"] = {"status": "done"}

    assert store.trash("abc123").outcome == rt.OUTCOME_PARTIAL


# ── verification ──────────────────────────────────────────────

def test_verify_confirms_a_full_purge_left_nothing_behind(store):
    store._records.append(make_record())
    store.purge("abc123", mode=rt.PURGE_FULL)

    result = store.verify("abc123")

    assert result["outcome"] == rt.OUTCOME_COMPLETE
    assert result["residue"] == []


def test_verify_finds_residue_the_ledger_did_not_mention(store, tmp_path):
    store._records.append(make_record())
    store.purge("abc123", mode=rt.PURGE_FULL)
    leftover = tmp_path / "clone_abc123"
    leftover.mkdir()
    store._workspaces["abc123"] = str(leftover)

    result = store.verify("abc123")

    assert result["outcome"] == rt.OUTCOME_UNRESOLVED
    assert "clone_workspace" in result["residue"]


def test_verify_does_not_treat_a_blocked_purge_as_an_erasure(store):
    store._records.append(make_record())
    store.place_hold("abc123", "legal")
    assert store.purge("abc123").outcome == rt.OUTCOME_BLOCKED

    result = store.verify("abc123")

    components = {c["component"] for c in result["checks"]}
    assert "audit_tombstone" not in components
    assert result["state"] == rt.STATE_ACTIVE


def test_verify_reports_a_payload_purge_as_partial(store):
    store._records.append(make_record())
    store.purge("abc123", mode=rt.PURGE_PAYLOAD)

    result = store.verify("abc123")

    assert result["outcome"] == rt.OUTCOME_PARTIAL


# ── policy sweep ──────────────────────────────────────────────

def test_dry_run_sweep_plans_without_changing_anything(store, monkeypatch):
    store._records.append(make_record("old", age_days=45))
    store._records.append(make_record("new", age_days=1))

    result = store.sweep(dry_run=True)

    assert result["dry_run"] is True
    assert [p["scan_id"] for p in result["planned"]] == ["old"]
    assert result["planned"][0]["action"] == "archive"
    assert store._records[0]["vulnerabilities"]      # untouched


def test_sweep_at_a_future_date_shows_the_whole_schedule(store):
    store._records.append(make_record("s1", age_days=1))

    now = store.sweep(dry_run=True)
    later = store.sweep(as_of=time.time() + 100 * DAY, dry_run=True)

    assert now["planned"] == []
    assert later["planned"][0]["action"] == "trash"


def test_sweep_execution_is_partial_when_a_hold_blocks_one_scan(store):
    store._records.append(make_record("due1", age_days=45))
    store._records.append(make_record("due2", age_days=45))
    store.place_hold("due2", "legal")

    result = store.sweep(dry_run=False)

    assert result["outcome"] == rt.OUTCOME_PARTIAL
    by_id = {r["scan_id"]: r["outcome"] for r in result["receipts"]}
    assert by_id["due1"] == rt.OUTCOME_COMPLETE
    assert by_id["due2"] == rt.OUTCOME_BLOCKED


def test_sweep_is_blocked_when_every_due_scan_is_held(store):
    store._records.append(make_record("due1", age_days=45))
    store.place_hold("due1", "legal")

    assert store.sweep(dry_run=False)["outcome"] == rt.OUTCOME_BLOCKED


def test_trashed_scans_become_purge_eligible_after_the_trash_window(store):
    store._records.append(make_record("s1", age_days=1))
    store.trash("s1")

    due = store.policy.due_action(
        store._records[0], time.time() + (store.policy.purge_after_days + 1) * DAY)

    assert due == "purge"


# ── audit ledger ──────────────────────────────────────────────

def test_every_operation_lands_in_the_ledger(store):
    store._records.append(make_record())
    store.archive("abc123")
    store.restore("abc123")
    store.trash("abc123")

    entries = store.ledger.read(scan_id="abc123")

    assert [e["operation"] for e in entries] == ["trash", "restore", "archive"]
    assert store.ledger.verify()["outcome"] == rt.OUTCOME_COMPLETE


def test_editing_a_past_ledger_entry_breaks_the_chain(store):
    store._records.append(make_record())
    store.archive("abc123")
    store.trash("abc123")

    lines = store.ledger.path.read_text().splitlines()
    first = json.loads(lines[0])
    first["actor"] = "somebody-else"
    lines[0] = json.dumps(first)
    store.ledger.path.write_text("\n".join(lines) + "\n")

    verdict = store.ledger.verify()

    assert verdict["outcome"] == rt.OUTCOME_UNRESOLVED
    assert verdict["broken"]


def test_deleting_a_ledger_entry_breaks_the_chain(store):
    store._records.append(make_record())
    store.archive("abc123")
    store.trash("abc123")

    lines = store.ledger.path.read_text().splitlines()
    store.ledger.path.write_text(lines[1] + "\n")

    assert store.ledger.verify()["outcome"] == rt.OUTCOME_UNRESOLVED


# ── inventory ─────────────────────────────────────────────────

def test_inventory_reports_state_counts_and_holds(store):
    store._records.append(make_record("a"))
    store._records.append(make_record("b"))
    store._records.append(make_record("c"))
    store.archive("b")
    store.trash("c")
    store.place_hold("a", "legal")

    inv = store.inventory()

    assert inv["counts"][rt.STATE_ACTIVE] == 1
    assert inv["counts"][rt.STATE_ARCHIVED] == 1
    assert inv["counts"][rt.STATE_TRASHED] == 1
    assert inv["held"] == 1
    assert inv["archive_files"] == 1


def test_inventory_can_be_filtered_to_one_state(store):
    store._records.append(make_record("a"))
    store._records.append(make_record("b"))
    store.trash("b")

    items = store.inventory(include_states=(rt.STATE_TRASHED,))["items"]

    assert [i["scan_id"] for i in items] == ["b"]


def test_unknown_scan_raises_rather_than_reporting_success(store):
    with pytest.raises(rt.RetentionError):
        store.trash("nope")


# ── rollup ────────────────────────────────────────────────────

def test_a_refusal_outranks_a_failure_in_the_rollup():
    components = [
        rt.ComponentResult("a", rt.C_UNRESOLVED, ""),
        rt.ComponentResult("b", rt.C_BLOCKED, ""),
    ]
    assert rt.rollup(components) == rt.OUTCOME_BLOCKED


def test_a_tombstone_alone_does_not_make_an_erasure_partial():
    components = [
        rt.ComponentResult("history_record", rt.C_DONE, ""),
        rt.ComponentResult("audit_tombstone", rt.C_POLICY, ""),
    ]
    assert rt.rollup(components) == rt.OUTCOME_COMPLETE
