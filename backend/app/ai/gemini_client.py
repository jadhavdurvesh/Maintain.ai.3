"""Optional online Gemini diagnostic layer for MAINTAIN AI."""
import json
import os
from typing import List, Optional

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _resolve_api_key(db=None) -> Optional[str]:
    if db is not None:
        from .. import settings_store
        stored = settings_store.get_setting(db, "gemini_api_key")
        if stored:
            return stored
    return os.getenv("GEMINI_API_KEY")


SYSTEM_INSTRUCTION = """You are the diagnostic assistant inside MAINTAIN AI, an industrial predictive-maintenance system.
Respond ONLY with strict JSON matching this shape:
{
  "safety_notice": "<one sentence safety reminder appropriate to the problem>",
  "needs_more_info": <true|false>,
  "clarifying_questions": ["<question>", ...],
  "possible_causes": [
    {"cause": "<short cause name>", "confidence": <0-100 integer>, "certainty": "<confirmed|likely|possible|insufficient_information>"}
  ],
  "recommended_procedure": ["<step 1>", "<step 2>", ...]
}

Diagnostic rules:
- Treat the supplied machine context as live evidence, not decoration.
- Use the supplied sensor_summary, recent faults, alerts, maintenance history, health score and operating hours when relevant.
- NEVER ask the technician for a value that is already present in sensor_summary. Instead, reference the known value and ask about the next missing or discriminating fact.
- Questions must be specific to the current problem, selected machine, observed evidence, and leading differential causes. Do not use a fixed questionnaire.
- Ask only the minimum number of high-value questions needed to distinguish between plausible causes. Usually ask 1-3 questions at a time.
- If the telemetry and technician answers are sufficient, stop asking questions and provide a ranked diagnosis and procedure.
- Do not repeat a question already answered in the conversation.
- A sensor trend is not available unless the context contains enough readings to support it. Do not invent trends.
- Never state a cause as confirmed unless the technician's words or supplied machine evidence actually confirms it.
- If there is insufficient information, set needs_more_info true and leave possible_causes and recommended_procedure empty rather than guessing.
- Always start a physical-inspection procedure with an isolation/lockout safety step when appropriate.
- Keep recommendations concrete and specific to industrial machinery.
"""


def diagnose_with_gemini(
    problem_description: str,
    machine_context: Optional[dict] = None,
    answers: Optional[List[str]] = None,
    db=None,
) -> Optional[dict]:
    api_key = _resolve_api_key(db)
    if not api_key:
        return None

    try:
        import google.generativeai as genai
    except ImportError:
        return None

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL, system_instruction=SYSTEM_INSTRUCTION)

        context_lines = []
        if machine_context:
            context_lines.append("Selected machine evidence:\n" + json.dumps(machine_context, default=str, indent=2))
        if answers:
            context_lines.append("Technician answers already provided:\n" + "\n".join(f"- {a}" for a in answers))

        prompt = (
            f"Current problem reported by technician:\n{problem_description}\n\n"
            + "\n\n".join(context_lines)
            + "\n\nUse the evidence above to continue this diagnostic session."
        )

        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        data["source"] = "gemini"
        return data
    except Exception:
        return None
