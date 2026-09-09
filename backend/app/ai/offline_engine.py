"""Offline, evidence-aware maintenance diagnostic engine."""
import json
import os
import sys
from typing import List, Optional

from sqlalchemy.orm import Session

from .. import models

if getattr(sys, "frozen", False):
    _KB_PATH = os.path.join(sys._MEIPASS, "app", "ai", "knowledge_base.json")
else:
    _KB_PATH = os.path.join(os.path.dirname(__file__), "knowledge_base.json")

SAFETY_NOTICE = (
    "Before physical inspection, ensure the equipment is in a safe state and "
    "follow the approved isolation and safety procedures."
)

GENERIC_QUESTIONS = [
    "What symptom is most noticeable right now (heat, noise, vibration, loss of output, or trip)?",
    "Did the symptom start suddenly or develop gradually?",
    "Did the operating load or duty cycle change before the problem started?",
]


def _load_kb() -> list:
    with open(_KB_PATH) as f:
        return json.load(f)


def _certainty_label(confidence: int) -> str:
    if confidence >= 85:
        return "confirmed"
    if confidence >= 60:
        return "likely"
    if confidence >= 30:
        return "possible"
    return "insufficient_information"


def _score_entry(entry: dict, text: str, answers: List[str]) -> int:
    text = text.lower()
    combined_answers = " ".join(answers).lower() if answers else ""
    score = 0
    for symptom in entry.get("symptoms", []):
        s = symptom.lower()
        if s in text:
            score += 2
        if s in combined_answers:
            score += 3
    return score


def _sensor_evidence(db: Optional[Session], machine_id: Optional[int]) -> dict:
    if not db or not machine_id:
        return {}
    readings = (
        db.query(models.SensorReading)
        .filter_by(machine_id=machine_id)
        .order_by(models.SensorReading.recorded_at.desc())
        .limit(30)
        .all()
    )
    evidence = {}
    for r in readings:
        kind = (r.reading_type or "").lower()
        if kind not in {"temperature", "vibration", "current", "load"} or kind in evidence:
            continue
        evidence[kind] = {"value": r.value, "unit": r.unit, "recorded_at": r.recorded_at}
    return evidence


def _adaptive_questions(entry: Optional[dict], answers: List[str], sensor_evidence: dict) -> list:
    if not entry:
        return GENERIC_QUESTIONS
    answered = " ".join(answers).lower()
    questions = []
    for q in entry.get("questions", []):
        if q.lower() in answered:
            continue
        q_lower = q.lower()
        # Do not ask for information that is already available from telemetry.
        if "temperature" in q_lower and "temperature" in sensor_evidence:
            continue
        if "load" in q_lower and "load" in sensor_evidence:
            continue
        if "vibration" in q_lower and "vibration" in sensor_evidence:
            continue
        questions.append(q)
    return questions


def diagnose(
    db: Optional[Session],
    machine_category: Optional[str],
    problem_description: str,
    answers: Optional[List[str]] = None,
    machine_id: Optional[int] = None,
) -> dict:
    answers = answers or []
    kb = _load_kb()
    candidates = [e for e in kb if not machine_category or e["machine_category"] == machine_category]
    if not candidates:
        candidates = kb

    scored = sorted(candidates, key=lambda e: _score_entry(e, problem_description, answers), reverse=True)
    best = scored[0] if scored else None
    top_score = _score_entry(best, problem_description, answers) if best else 0
    sensor_evidence = _sensor_evidence(db, machine_id)

    if not best or top_score == 0:
        return {
            "safety_notice": SAFETY_NOTICE,
            "clarifying_questions": GENERIC_QUESTIONS,
            "possible_causes": [],
            "recommended_procedure": [],
            "source": "offline",
            "needs_more_info": True,
        }

    questions = _adaptive_questions(best, answers, sensor_evidence)
    if top_score < 4 and questions:
        return {
            "safety_notice": SAFETY_NOTICE,
            "clarifying_questions": questions[:3],
            "possible_causes": [],
            "recommended_procedure": [],
            "source": "offline",
            "needs_more_info": True,
        }

    causes = [
        {
            "cause": c["cause"],
            "confidence": c["confidence"],
            "certainty": _certainty_label(c["confidence"]),
        }
        for c in best.get("causes", [])
    ]
    causes.sort(key=lambda c: c["confidence"], reverse=True)

    return {
        "safety_notice": SAFETY_NOTICE,
        "clarifying_questions": [],
        "possible_causes": causes,
        "recommended_procedure": best.get("recommended_procedure", []),
        "source": "offline",
        "needs_more_info": False,
    }
