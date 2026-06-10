"""
SentinelAI — FastAPI backend

── VulnSentinel (code security) ──────────────────────────────
POST /api/scan              Start a scan; returns scan_id + ws_url
WS   /ws/{scan_id}          Stream real-time agent logs
GET  /api/report/{scan_id}  Fetch completed report JSON
GET  /api/scans             List all scans

── ExamGuard (exam integrity) ────────────────────────────────
POST /api/exam/session          Create exam session; returns exam_id + ws_url
WS   /ws/exam/{exam_id}         Bidirectional: browser sends events → server sends immediate alerts
POST /api/exam/{exam_id}/analyze  Trigger LangGraph post-session analysis
WS   /ws/exam/{exam_id}/analysis  Stream analysis progress (mirrors VulnSentinel WS pattern)
GET  /api/exam/report/{exam_id}   Fetch completed integrity report
GET  /api/exam/sessions           List all exam sessions

── Shared ────────────────────────────────────────────────────
GET  /health

WebSocket message envelopes
───────────────────────────
VulnSentinel:
  server→client  { type: "update"|"done"|"error"|"ping", ... }

ExamGuard event socket (/ws/exam/{id}):
  client→server  { type: "tab_event"|"face_event"|"keystroke_stats"|"copy_paste"|"end_exam"|"ping" }
  server→client  { type: "immediate_alert"|"exam_ended"|"pong"|"error" }

ExamGuard analysis socket (/ws/exam/{id}/analysis):
  server→client  { type: "analysis_update"|"done"|"error"|"ping" }
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from agents.orchestrator import _graph, _initial_state
from tools.url_guard import assert_safe_target, UnsafeTargetError
from tools.git_cloner import cleanup_repo
from exam_agents.exam_pipeline import _exam_graph, stream_exam_analysis
from exam_agents.exam_state import ExamSession
from exam_agents.event_rules import (
    check_copy_paste,
    check_face_event,
    check_tab_event,
    check_absence_duration,
    check_phone_detected,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("sentinelai")

# ── Operational limits (overridable via environment) ──────────
MAX_CONCURRENT_SCANS   = int(os.getenv("MAX_CONCURRENT_SCANS", "3"))
SCAN_TIMEOUT_SECS      = float(os.getenv("SCAN_TIMEOUT_SECS", "600"))
ANALYSIS_TIMEOUT_SECS  = float(os.getenv("ANALYSIS_TIMEOUT_SECS", "300"))
SESSION_TTL_SECS       = float(os.getenv("SESSION_TTL_SECS", str(24 * 3600)))
JANITOR_INTERVAL_SECS  = float(os.getenv("JANITOR_INTERVAL_SECS", "600"))
MAX_EVENTS_PER_LIST    = int(os.getenv("MAX_EVENTS_PER_LIST", "5000"))

# Phone detection runs client-side (coco-ssd in the browser); the browser
# sends a `phone_detected` event, handled below. No server-side ML needed.

# ── In-process registries ─────────────────────────────────────
_scans: Dict[str, dict] = {}           # VulnSentinel scan sessions
_exam_sessions: Dict[str, dict] = {}   # ExamGuard sessions


# ══════════════════════════════════════════════════════════════
#  App lifecycle
# ══════════════════════════════════════════════════════════════

async def _janitor() -> None:
    """Periodically purge finished scans/sessions older than SESSION_TTL_SECS."""
    while True:
        await asyncio.sleep(JANITOR_INTERVAL_SECS)
        cutoff = time.time() - SESSION_TTL_SECS
        for sid in [s for s, d in _scans.items()
                    if d["status"] in ("done", "error") and d["started_at"] < cutoff]:
            _scans.pop(sid, None)
            logger.info("Janitor: purged expired scan %s", sid)
        for eid in [e for e, d in _exam_sessions.items()
                    if d["session"]["status"] in ("done", "error") and d["started_at"] < cutoff]:
            _exam_sessions.pop(eid, None)
            logger.info("Janitor: purged expired exam session %s", eid)


@asynccontextmanager
async def lifespan(app: FastAPI):
    janitor = asyncio.create_task(_janitor())
    yield
    janitor.cancel()
    _scans.clear()
    _exam_sessions.clear()


app = FastAPI(title="SentinelAI", version="0.1.0", lifespan=lifespan)

_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
# ALLOWED_ORIGIN_REGEX is handy for Vercel preview URLs, e.g.
#   https://.*\.vercel\.app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()],
    allow_origin_regex=os.getenv("ALLOWED_ORIGIN_REGEX") or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════
#  Pydantic models
# ══════════════════════════════════════════════════════════════

class ScanRequest(BaseModel):
    repo_url: str = Field(min_length=4, max_length=2048)

    @field_validator("repo_url")
    @classmethod
    def must_be_https_url(cls, v: str) -> str:
        v = v.strip()
        if v.startswith(("http://", "https://")):
            return v
        # Bare domain like "example.com" — scheme is added downstream
        if "://" not in v and " " not in v and "." in v:
            return v
        raise ValueError("repo_url must be an http(s) URL or a bare domain")


class ScanResponse(BaseModel):
    scan_id: str
    ws_url: str
    status: str


class ScanSummary(BaseModel):
    scan_id: str
    repo_url: str
    status: str
    started_at: float


# ══════════════════════════════════════════════════════════════
#  Background task
# ══════════════════════════════════════════════════════════════

async def _run_scan(repo_url: str, scan_id: str) -> None:
    queue: asyncio.Queue = _scans[scan_id]["queue"]
    accumulated: dict = {}

    try:
        state = _initial_state(repo_url, scan_id)
        config = {"configurable": {"thread_id": scan_id}}

        async with asyncio.timeout(SCAN_TIMEOUT_SECS):
            async for event in _graph.astream(state, config=config):
                node_name, node_output = next(iter(event.items()))

                # Merge into accumulated so we can retrieve the report at the end.
                # agent_logs uses operator.add so we handle it manually.
                for k, v in node_output.items():
                    if k == "agent_logs":
                        accumulated.setdefault("agent_logs", [])
                        accumulated["agent_logs"].extend(v)
                    else:
                        accumulated[k] = v

                await queue.put({
                    "type": "update",
                    "node": node_name,
                    "logs": node_output.get("agent_logs", []),
                    "status": node_output.get("status", ""),
                    "scan_id": scan_id,
                })

        report = accumulated.get("report", {})
        _scans[scan_id]["report"] = report
        _scans[scan_id]["status"] = "done"

        await queue.put({"type": "done", "scan_id": scan_id, "report": report})

    except TimeoutError:
        logger.error("Scan %s exceeded %ss timeout", scan_id, SCAN_TIMEOUT_SECS)
        _scans[scan_id]["status"] = "error"
        await queue.put({"type": "error", "scan_id": scan_id,
                         "message": f"Scan timed out after {int(SCAN_TIMEOUT_SECS)}s"})

    except Exception:
        logger.exception("Scan %s crashed", scan_id)
        _scans[scan_id]["status"] = "error"
        await queue.put({"type": "error", "scan_id": scan_id,
                         "message": "Scan failed due to an internal error — see server logs"})

    finally:
        cleanup_repo(scan_id)  # remove cloned repo, if any
        await queue.put(None)  # sentinel — unblocks the WebSocket reader


# ══════════════════════════════════════════════════════════════
#  REST endpoints
# ══════════════════════════════════════════════════════════════

@app.post("/api/scan", response_model=ScanResponse, status_code=201)
async def start_scan(req: ScanRequest) -> ScanResponse:
    active = sum(1 for s in _scans.values() if s["status"] not in ("done", "error"))
    if active >= MAX_CONCURRENT_SCANS:
        raise HTTPException(status_code=429,
                            detail=f"Too many scans in progress ({active}/{MAX_CONCURRENT_SCANS}) — try again shortly")

    try:
        # Resolve in a thread — getaddrinfo blocks
        await asyncio.get_running_loop().run_in_executor(None, assert_safe_target, req.repo_url)
    except UnsafeTargetError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    scan_id = str(uuid.uuid4())[:8]
    _scans[scan_id] = {
        "queue": asyncio.Queue(),
        "report": None,
        "status": "starting",
        "repo_url": req.repo_url,
        "started_at": time.time(),
    }
    asyncio.create_task(_run_scan(req.repo_url, scan_id))
    logger.info("Scan %s started for %s", scan_id, req.repo_url)
    return ScanResponse(scan_id=scan_id, ws_url=f"/ws/{scan_id}", status="starting")


@app.get("/api/report/{scan_id}")
async def get_report(scan_id: str) -> dict:
    scan = _scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan["status"] in ("starting", "scanning", "analyzing", "exploiting", "patching", "reporting"):
        raise HTTPException(status_code=202, detail=f"Scan in progress: {scan['status']}")
    if scan["status"] == "error":
        raise HTTPException(status_code=500, detail="Scan failed — check WebSocket logs")
    return scan["report"]


@app.get("/api/scans", response_model=list[ScanSummary])
async def list_scans() -> list[ScanSummary]:
    return [
        ScanSummary(
            scan_id=sid,
            repo_url=data["repo_url"],
            status=data["status"],
            started_at=data["started_at"],
        )
        for sid, data in sorted(_scans.items(), key=lambda x: x[1]["started_at"], reverse=True)
    ]


@app.get("/health")
async def health() -> dict:
    from agents.llm_router import get_active_backend
    return {
        "status": "ok",
        "version": app.version,
        "llm_backend": get_active_backend(),
        "active_scans": sum(1 for s in _scans.values() if s["status"] not in ("done", "error")),
        "active_exam_sessions": sum(
            1 for e in _exam_sessions.values() if e["session"]["status"] == "active"
        ),
    }


# ══════════════════════════════════════════════════════════════
#  WebSocket endpoint
# ══════════════════════════════════════════════════════════════

PING_INTERVAL = 30.0   # seconds between keepalive pings
WS_TIMEOUT    = 600.0  # max seconds to wait for a queue message before giving up

@app.websocket("/ws/{scan_id}")
async def ws_scan_feed(websocket: WebSocket, scan_id: str) -> None:
    if scan_id not in _scans:
        await websocket.close(code=4004, reason="Scan not found")
        return

    await websocket.accept()
    logger.info("WS client connected for scan %s", scan_id)

    queue: asyncio.Queue = _scans[scan_id]["queue"]
    deadline = time.monotonic() + WS_TIMEOUT

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning("Scan %s timed out", scan_id)
                await websocket.send_json({"type": "error", "message": "Scan timed out", "scan_id": scan_id})
                break

            try:
                msg = await asyncio.wait_for(queue.get(), timeout=min(PING_INTERVAL, remaining))
            except asyncio.TimeoutError:
                # Send a keepalive so the browser doesn't drop the connection
                await websocket.send_json({"type": "ping"})
                continue

            if msg is None:
                # Sentinel from the background task — scan finished or errored
                break

            await websocket.send_json(msg)

            if msg.get("type") in ("done", "error"):
                break

    except WebSocketDisconnect:
        logger.info("WS client disconnected from scan %s", scan_id)
    except Exception as exc:
        logger.error("WS error for scan %s: %s", scan_id, exc)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
        logger.info("WS connection closed for scan %s", scan_id)


# ══════════════════════════════════════════════════════════════
#  ExamGuard — Pydantic models
# ══════════════════════════════════════════════════════════════

class ExamSessionRequest(BaseModel):
    student_id:       str = Field(min_length=1, max_length=100)
    student_name:     str = Field(min_length=1, max_length=200)
    exam_name:        str = Field(min_length=1, max_length=200)
    duration_minutes: int = Field(default=60, ge=1, le=600)


class ExamSessionResponse(BaseModel):
    exam_id:    str
    ws_url:     str
    status:     str


class ExamSessionSummary(BaseModel):
    exam_id:      str
    student_name: str
    exam_name:    str
    status:       str
    started_at:   float


# ══════════════════════════════════════════════════════════════
#  ExamGuard — REST endpoints
# ══════════════════════════════════════════════════════════════

@app.post("/api/exam/session", response_model=ExamSessionResponse, status_code=201)
async def create_exam_session(req: ExamSessionRequest) -> ExamSessionResponse:
    exam_id = str(uuid.uuid4())[:8]
    now     = time.time()

    session: ExamSession = ExamSession(
        exam_id=exam_id,
        student_id=req.student_id,
        student_name=req.student_name,
        exam_name=req.exam_name,
        duration_minutes=req.duration_minutes,
        started_at=now,
        ended_at=None,
        tab_events=[],
        face_events=[],
        keystroke_stats=None,
        copy_paste_events=[],
        immediate_alerts=[],
        behavior_flags=[],
        anomaly_scores=[],
        alerts=[],
        integrity_score=100.0,
        verdict="CLEAN",
        report={},
        status="active",
        errors=[],
        agent_logs=[f"[SessionMonitor] Session {exam_id} created for {req.student_name}"],
    )

    _exam_sessions[exam_id] = {
        "session":        session,
        "analysis_queue": asyncio.Queue(),
        "monitor_queues": [],     # fan-out queues for invigilator monitor connections
        "absent_since":   None,   # tracks continuous face-absent window
        "started_at":     now,
    }

    logger.info("Exam session %s created for student %s", exam_id, req.student_id)
    return ExamSessionResponse(exam_id=exam_id, ws_url=f"/ws/exam/{exam_id}", status="active")


@app.get("/api/exam/session/{exam_id}")
async def get_exam_session(exam_id: str) -> dict:
    entry = _exam_sessions.get(exam_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Exam session not found")
    s = entry["session"]
    return {
        "exam_id":          exam_id,
        "student_name":     s["student_name"],
        "exam_name":        s["exam_name"],
        "duration_minutes": s["duration_minutes"],
        "status":           s["status"],
    }


@app.post("/api/exam/{exam_id}/analyze", status_code=202)
async def trigger_analysis(exam_id: str) -> dict:
    entry = _exam_sessions.get(exam_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Exam session not found")

    session = entry["session"]
    if session["status"] == "analyzing":
        # Analysis already running — don't spawn a duplicate pipeline
        return {"exam_id": exam_id, "status": "analyzing", "ws_url": f"/ws/exam/{exam_id}/analysis"}

    if session["status"] == "active":
        session["status"]   = "ended"
        session["ended_at"] = time.time()

    session["status"] = "analyzing"
    asyncio.create_task(_run_exam_analysis(exam_id))
    return {"exam_id": exam_id, "status": "analyzing", "ws_url": f"/ws/exam/{exam_id}/analysis"}


@app.get("/api/exam/report/{exam_id}")
async def get_exam_report(exam_id: str) -> dict:
    entry = _exam_sessions.get(exam_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Exam session not found")
    session = entry["session"]
    if session["status"] in ("active", "ended", "analyzing"):
        raise HTTPException(status_code=202, detail=f"Analysis in progress: {session['status']}")
    if session["status"] == "error":
        raise HTTPException(status_code=500, detail="Analysis failed")
    return session["report"]


@app.get("/api/exam/sessions", response_model=list[ExamSessionSummary])
async def list_exam_sessions() -> list[ExamSessionSummary]:
    return [
        ExamSessionSummary(
            exam_id=eid,
            student_name=e["session"]["student_name"],
            exam_name=e["session"]["exam_name"],
            status=e["session"]["status"],
            started_at=e["started_at"],
        )
        for eid, e in sorted(
            _exam_sessions.items(), key=lambda x: x[1]["started_at"], reverse=True
        )
    ]


# ══════════════════════════════════════════════════════════════
#  ExamGuard — background analysis task
# ══════════════════════════════════════════════════════════════

async def _run_exam_analysis(exam_id: str) -> None:
    entry   = _exam_sessions[exam_id]
    session = entry["session"]
    queue   = entry["analysis_queue"]

    try:
        config      = {"configurable": {"thread_id": exam_id}}
        accumulated: dict = {}

        async with asyncio.timeout(ANALYSIS_TIMEOUT_SECS):
            async for event in _exam_graph.astream(session, config=config):
                node_name, node_output = next(iter(event.items()))

                # Accumulate full node output so report/score/verdict are captured
                for k, v in node_output.items():
                    if k == "agent_logs":
                        accumulated.setdefault("agent_logs", [])
                        accumulated["agent_logs"].extend(v if isinstance(v, list) else [v])
                    else:
                        accumulated[k] = v

                await queue.put({
                    "type":    "analysis_update",
                    "node":    node_name,
                    "logs":    node_output.get("agent_logs", []),
                    "status":  node_output.get("status", ""),
                    "exam_id": exam_id,
                })

        # Persist final state back into the live session object
        for field in ("report", "verdict", "integrity_score", "behavior_flags",
                      "anomaly_scores", "alerts"):
            if field in accumulated:
                session[field] = accumulated[field]

        session["status"] = "done"
        await queue.put({
            "type":    "done",
            "exam_id": exam_id,
            "report":  session["report"],
        })

    except TimeoutError:
        logger.error("Exam analysis %s exceeded %ss timeout", exam_id, ANALYSIS_TIMEOUT_SECS)
        session["status"] = "error"
        await queue.put({"type": "error", "exam_id": exam_id,
                         "message": f"Analysis timed out after {int(ANALYSIS_TIMEOUT_SECS)}s"})

    except Exception:
        logger.exception("Exam analysis %s crashed", exam_id)
        session["status"] = "error"
        await queue.put({"type": "error", "exam_id": exam_id,
                         "message": "Analysis failed due to an internal error — see server logs"})

    finally:
        await queue.put(None)


async def _fan_out(entry: dict, msg: dict) -> None:
    """Push a message to all connected invigilator monitor queues."""
    for q in list(entry["monitor_queues"]):
        await q.put(msg)


# ══════════════════════════════════════════════════════════════
#  ExamGuard — bidirectional event WebSocket
#  Browser sends events; server applies rule checks and sends
#  immediate alerts back in real-time.
# ══════════════════════════════════════════════════════════════

def _append_capped(lst: list, item: dict) -> None:
    """Append an event, dropping the oldest beyond MAX_EVENTS_PER_LIST."""
    lst.append(item)
    if len(lst) > MAX_EVENTS_PER_LIST:
        del lst[: len(lst) - MAX_EVENTS_PER_LIST]


@app.websocket("/ws/exam/{exam_id}")
async def ws_exam_events(websocket: WebSocket, exam_id: str) -> None:
    entry = _exam_sessions.get(exam_id)
    if not entry:
        await websocket.close(code=4004, reason="Exam session not found")
        return
    if entry["session"]["status"] != "active":
        await websocket.close(code=4003, reason="Exam session is no longer active")
        return

    await websocket.accept()
    session: ExamSession = entry["session"]
    logger.info("Exam event WS connected for session %s", exam_id)

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=PING_INTERVAL)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                # Check for prolonged face absence even with no new events
                if entry["absent_since"] is not None:
                    alert = check_absence_duration(entry["absent_since"])
                    if alert:
                        await websocket.send_json(alert)
                        session["immediate_alerts"].append(alert)
                continue

            event_type = data.get("type")

            # ── Tab events ───────────────────────────────────
            if event_type == "tab_event":
                _append_capped(session["tab_events"], data)
                blur_count = sum(
                    1 for e in session["tab_events"]
                    if e.get("event_type") in ("blur", "hidden")
                )
                alert = check_tab_event(blur_count, data.get("timestamp", time.time()))
                if alert:
                    await websocket.send_json(alert)
                    session["immediate_alerts"].append(alert)
                    await _fan_out(entry, alert)

            # ── Face events ──────────────────────────────────
            elif event_type == "face_event":
                _append_capped(session["face_events"], data)
                face_count = data.get("face_count", 1)
                confidence = data.get("confidence", 1.0)
                ts         = data.get("timestamp", time.time())

                if face_count == 0:
                    if entry["absent_since"] is None:
                        entry["absent_since"] = ts
                    else:
                        alert = check_absence_duration(entry["absent_since"], ts)
                        if alert:
                            await websocket.send_json(alert)
                            session["immediate_alerts"].append(alert)
                            await _fan_out(entry, alert)
                else:
                    entry["absent_since"] = None   # face back in frame

                alert = check_face_event(face_count, confidence, ts)
                if alert:
                    await websocket.send_json(alert)
                    session["immediate_alerts"].append(alert)
                    await _fan_out(entry, alert)

            # ── Keystroke stats ──────────────────────────────
            elif event_type == "keystroke_stats":
                session["keystroke_stats"] = data

            # ── Copy-paste ───────────────────────────────────
            elif event_type == "copy_paste":
                _append_capped(session["copy_paste_events"], data)
                count = len(session["copy_paste_events"])
                alert = check_copy_paste(count, data.get("timestamp", time.time()))
                if alert:
                    await websocket.send_json(alert)
                    session["immediate_alerts"].append(alert)
                    await _fan_out(entry, alert)

            # ── Phone detection (client-side coco-ssd) ───────
            elif event_type == "phone_detected":
                _append_capped(session.setdefault("phone_events", []), data)
                phone_count = len(session["phone_events"])
                confidence  = data.get("confidence", 0.0)
                alert = check_phone_detected(phone_count, confidence, data.get("timestamp", time.time()))
                if alert:
                    await websocket.send_json(alert)
                    session["immediate_alerts"].append(alert)
                    await _fan_out(entry, alert)

            # ── End exam ─────────────────────────────────────
            elif event_type == "end_exam":
                session["status"]   = "ended"
                session["ended_at"] = time.time()
                ended_msg = {
                    "type":    "exam_ended",
                    "exam_id": exam_id,
                    "message": "Exam ended. Run POST /api/exam/{exam_id}/analyze to generate the integrity report.",
                }
                await websocket.send_json(ended_msg)
                await _fan_out(entry, ended_msg)
                break

            # ── Keepalive ────────────────────────────────────
            elif event_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info("Exam event WS disconnected for %s", exam_id)
    except Exception:
        logger.exception("Exam event WS error for %s", exam_id)
        try:
            await websocket.send_json({"type": "error", "message": "Internal error processing exam events"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  ExamGuard — invigilator monitor WebSocket
#  One-directional: server fans out immediate alerts and
#  exam_ended events to the invigilator dashboard in real-time.
# ══════════════════════════════════════════════════════════════

@app.websocket("/ws/exam/{exam_id}/monitor")
async def ws_exam_monitor(websocket: WebSocket, exam_id: str) -> None:
    entry = _exam_sessions.get(exam_id)
    if not entry:
        await websocket.close(code=4004, reason="Exam session not found")
        return

    await websocket.accept()
    q: asyncio.Queue = asyncio.Queue()
    entry["monitor_queues"].append(q)
    logger.info("Monitor WS connected for exam %s", exam_id)

    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=PING_INTERVAL)
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            if msg is None:
                break

            await websocket.send_json(msg)

    except WebSocketDisconnect:
        logger.info("Monitor WS disconnected for exam %s", exam_id)
    except Exception as exc:
        logger.error("Monitor WS error for exam %s: %s", exam_id, exc)
    finally:
        if q in entry["monitor_queues"]:
            entry["monitor_queues"].remove(q)
        try:
            await websocket.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  ExamGuard — analysis progress WebSocket
#  One-directional: server streams LangGraph node progress
#  to the invigilator dashboard after analysis is triggered.
# ══════════════════════════════════════════════════════════════

@app.websocket("/ws/exam/{exam_id}/analysis")
async def ws_exam_analysis(websocket: WebSocket, exam_id: str) -> None:
    entry = _exam_sessions.get(exam_id)
    if not entry:
        await websocket.close(code=4004, reason="Exam session not found")
        return

    await websocket.accept()
    queue: asyncio.Queue = entry["analysis_queue"]
    deadline = time.monotonic() + WS_TIMEOUT

    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                await websocket.send_json({"type": "error", "message": "Analysis timed out"})
                break

            try:
                msg = await asyncio.wait_for(queue.get(), timeout=min(PING_INTERVAL, remaining))
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                continue

            if msg is None:
                break

            await websocket.send_json(msg)

            if msg.get("type") in ("done", "error"):
                break

    except WebSocketDisconnect:
        logger.info("Analysis WS disconnected for exam %s", exam_id)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
