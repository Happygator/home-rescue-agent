"""Safety callback to intercept dangerous DIY repairs (gas, high voltage, refrigerant, leaks on electrics)."""
from __future__ import annotations

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import types


async def before_model_callback(
    callback_context: CallbackContext, llm_request: LlmRequest
) -> LlmResponse | None:
    """Intercept dangerous troubleshooting steps and return a refusal response."""
    user_texts = []
    for content in llm_request.contents:
        if content.role == "user" or not content.role:
            for part in content.parts:
                if part.text:
                    user_texts.append(part.text.lower())

    combined_input = " ".join(user_texts)

    is_dangerous = False
    refusal_reason = ""

    # 1. Gas lines/components
    gas_keywords = ["gas", "burner", "igniter", "pilot light", "propane", "natural gas", "gas leak"]
    if any(k in combined_input for k in gas_keywords):
        is_dangerous = True
        refusal_reason = "gas system handling"

    # 2. Internal wiring / mains voltage (testing live voltage, capacitors)
    voltage_keywords = ["live wires", "capacitor", "electric board", "high voltage", "heating element", "power outlet"]
    if any(k in combined_input for k in voltage_keywords):
        is_dangerous = True
        refusal_reason = "high-voltage electrical work"

    # 3. Sealed refrigerant system
    refrigerant_keywords = ["refrigerant", "freon", "coolant", "compressor leak", "evaporator coil puncture", "sealed system", "charging refrigerant"]
    if any(k in combined_input for k in refrigerant_keywords):
        is_dangerous = True
        refusal_reason = "sealed refrigerant system work"

    # 4. Water leaking onto electrical parts
    water_elec_keywords = ["water on board", "water leaking on wire", "wet wires", "water leak electrical", "water leaking onto electrical"]
    if any(k in combined_input for k in water_elec_keywords):
        is_dangerous = True
        refusal_reason = "water leakage onto live electrical components"

    if is_dangerous:
        # Create draft escalation if case_id is available in state
        case_id = callback_context.state.get("case_id")
        recap_msg = ""
        if case_id:
            from appliance_fixer.case_store import CaseStore
            from appliance_fixer.tools import draft_escalation
            db_path = callback_context.state.get("db_path", "appliance_fixer.db")
            store = CaseStore(db_path)
            draft_escalation(case_id, store)
            recap_msg = f" Case {case_id} has been escalated to a professional."

        refusal_text = (
            f"Safety Alert: The requested action involves {refusal_reason}, "
            f"which is unsafe for DIY troubleshooting. For your safety, I cannot guide you through this procedure. "
            f"This case has been escalated to a professional technician.{recap_msg}"
        )

        content = types.Content(
            role="model",
            parts=[types.Part.from_text(text=refusal_text)]
        )
        return LlmResponse(content=content)

    return None
