"""
Immediate rule-based alerting — fires synchronously on every
incoming browser event before the LangGraph pipeline runs.
These alerts appear on the invigilator dashboard in real-time
without waiting for the full post-session analysis.
"""

from __future__ import annotations

import time
from typing import Optional

# Thresholds
TAB_SWITCH_WARN     = 3    # warn after N tab switches
TAB_SWITCH_CRITICAL = 7
FACE_ABSENT_WARN_S  = 10   # warn if face absent for N continuous seconds
FACE_ABSENT_CRIT_S  = 30
COPY_PASTE_WARN     = 2
COPY_PASTE_CRITICAL = 5


def check_tab_event(tab_blur_count: int, timestamp: float) -> Optional[dict]:
    if tab_blur_count == TAB_SWITCH_WARN:
        return _alert("WARNING", "Repeated Tab Switching",
                      f"Student has switched away from the exam {tab_blur_count} times.",
                      "Monitor closely — may be referencing external material.",
                      timestamp)
    if tab_blur_count == TAB_SWITCH_CRITICAL:
        return _alert("CRITICAL", "Excessive Tab Switching",
                      f"Student has switched away {tab_blur_count} times — strong cheating signal.",
                      "Consider flagging the attempt and notifying the exam coordinator.",
                      timestamp)
    return None


def check_face_event(face_count: int, confidence: float, timestamp: float) -> Optional[dict]:
    if face_count == 0 and confidence >= 0.7:
        return _alert("WARNING", "Face Not Detected",
                      "Camera cannot detect the student's face.",
                      "Ask the student to reposition — or flag if persistent.",
                      timestamp)
    if face_count > 1:
        sev = "CRITICAL" if face_count >= 3 else "WARNING"
        return _alert(sev, "Multiple Faces Detected",
                      f"{face_count} faces visible — possible impersonation or collaboration.",
                      "Immediately verify the student's identity.",
                      timestamp)
    return None


def check_copy_paste(count: int, timestamp: float) -> Optional[dict]:
    if count == COPY_PASTE_WARN:
        return _alert("WARNING", "Copy-Paste Detected",
                      f"Student has pasted content {count} times.",
                      "Review pasted content for plagiarism post-exam.",
                      timestamp)
    if count == COPY_PASTE_CRITICAL:
        return _alert("CRITICAL", "Excessive Copy-Paste",
                      f"Student has pasted content {count} times — likely using external sources.",
                      "Flag the attempt immediately.",
                      timestamp)
    return None


def check_phone_detected(count: int, confidence: float, timestamp: float) -> Optional[dict]:
    """Fire a CRITICAL alert the first time a phone is detected, WARNING on subsequent ones."""
    if count == 1:
        return _alert("WARNING", "Mobile Phone Detected",
                      f"A mobile phone was detected in the camera frame (confidence {confidence:.0%}).",
                      "Warn the student to remove the phone from view immediately.",
                      timestamp)
    if count >= 2:
        return _alert("CRITICAL", "Repeated Phone Use",
                      f"Mobile phone detected {count} times during the exam (confidence {confidence:.0%}).",
                      "Flag the session and notify the exam coordinator.",
                      timestamp)
    return None


def check_absence_duration(absent_since: float, now: Optional[float] = None) -> Optional[dict]:
    duration = (now or time.time()) - absent_since
    if FACE_ABSENT_WARN_S <= duration < FACE_ABSENT_CRIT_S:
        return _alert("WARNING", "Prolonged Face Absence",
                      f"Face not detected for {duration:.0f} seconds.",
                      "Check if student has left the camera frame.",
                      absent_since + duration)
    if duration >= FACE_ABSENT_CRIT_S:
        return _alert("CRITICAL", "Student May Have Left",
                      f"Face absent for {duration:.0f} seconds — student may have left their seat.",
                      "Intervene immediately.",
                      absent_since + duration)
    return None


# ── Internal ──────────────────────────────────────────────────

def _alert(severity: str, title: str, message: str, action: str, ts: float) -> dict:
    return {
        "type":               "immediate_alert",
        "severity":           severity,
        "title":              title,
        "message":            message,
        "recommended_action": action,
        "timestamp":          ts,
    }
