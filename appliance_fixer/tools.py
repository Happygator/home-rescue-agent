"""Tools for Appliance Fixer: model plate reading, model validation, and escalation drafting."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from google import genai
from google.genai import types

# Supported model numbers in the system (normalized)
SUPPORTED_MODELS = {
    "SAMSUNG": ["RSG257", "RF263", "RF28T5001SR"],
    "GE": ["GSS25"],
    "WHIRLPOOL": ["WRS555", "WRFF3336SZ", "WFW95HEDW0"],
    "MAYTAG": ["MFI257"],
    "LG": ["LFXS26", "LDFC2423V", "WM3500"],
    "FRIGIDAIRE": ["FFHB2750"],
    "KITCHENAID": ["KDTM354"],
    "BOSCH": ["BC-70-62H-US(E)", "SHX863"],
    "TRANE": ["4TTR6048J1000AA"]
}

# Support contacts for escalation
SUPPORT_CONTACTS = {
    "SAMSUNG": "support@samsung.com",
    "GE": "support@geappliances.com",
    "WHIRLPOOL": "support@whirlpool.com",
    "MAYTAG": "support@maytag.com",
    "LG": "support@lg.com",
    "FRIGIDAIRE": "support@frigidaire.com",
    "KITCHENAID": "support@kitchenaid.com",
    "BOSCH": "support@bosch-home.com",
    "TRANE": "support@trane.com"
}


def load_key() -> str:
    """Load Gemini API Key from file or environment variables."""
    # Find repository root (parent of appliance_fixer folder)
    root = Path(__file__).resolve().parent.parent
    f = root / "GEMINI_KEY.txt"
    raw = ""
    if f.exists():
        raw = f.read_text(encoding="utf-8").strip()
    if not raw:
        raw = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not raw:
        raise RuntimeError("No Gemini API key found. Place it in GEMINI_KEY.txt or set GOOGLE_API_KEY.")
    
    # Tolerate 'KEY=value' format
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GEMINI_KEY"):
        if raw.upper().startswith(name + "="):
            raw = raw.split("=", 1)[1].strip()
    return raw.strip().strip('"').strip("'").strip()


def normalize_model(s: str) -> str:
    """Normalize a model number string for comparison."""
    if not s:
        return ""
    s = str(s).upper()
    s = "".join(ch for ch in s if not ch.isspace())
    if "/" in s:  # drop region suffix like /AA
        s = s.split("/", 1)[0]
    if len(s) > 4 and s.endswith("00"):  # drop trailing revision 00
        s = s[:-2]
    # Keep only alphanumeric and standard model chars
    keep = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-()")
    return "".join(ch for ch in s if ch in keep)


def canonicalize_symbols(s: str) -> str:
    """Replace commonly confused OCR characters like O->0 and I/L->1."""
    if not s:
        return ""
    # Map O to 0, and I & L to 1 for robust membership checks
    return s.replace("O", "0").replace("I", "1").replace("L", "1")


def validate_model(model_number: str, brand: str | None = None) -> str | None:
    """Validate model number against supported brands and models.

    Applies normalizations and handles OCR confusions (O/0, I/1).
    Returns the exact supported model number if found, otherwise None.
    """
    norm_input = normalize_model(model_number)
    canon_input = canonicalize_symbols(norm_input)
    if not canon_input:
        return None

    # Search for match in supported models
    for b, models in SUPPORTED_MODELS.items():
        if brand and brand.upper() != b:
            continue
        for m in models:
            norm_supported = normalize_model(m)
            canon_supported = canonicalize_symbols(norm_supported)
            if canon_input == canon_supported or canon_input in canon_supported or canon_supported in canon_input:
                return m
    return None


def read_plate(photo_path: str | Path) -> dict:
    """Send spec plate photo to Gemini Vision to extract brand and model number."""
    photo_path = Path(photo_path)
    if not photo_path.exists():
        raise FileNotFoundError(f"Photo file not found: {photo_path}")

    client = genai.Client(api_key=load_key())
    
    prompt = (
        "You are reading the data/spec plate of a household appliance from a photo. "
        "Identify the BRAND and the MODEL number (manufacturer model code, NOT the serial number, "
        "NOT the part number). Also identify any visible error code if mentioned on the display in the photo. "
        "Respond with ONLY compact JSON, no markdown blocks, no prose: "
        '{"brand": <string or null>, "model_number": <string or null>, "error_code": <string or null>}.'
    )

    part = types.Part.from_bytes(data=photo_path.read_bytes(), mime_type="image/jpeg")
    
    # Generate content using gemini-2.5-flash
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[part, prompt]
    )
    
    text = (response.text or "").strip()
    
    # Strip markdown block if present
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
        
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return {"brand": None, "model_number": None, "error_code": None}

    try:
        parsed = json.loads(text[start:end + 1])
        return {
            "brand": parsed.get("brand"),
            "model_number": parsed.get("model_number"),
            "error_code": parsed.get("error_code")
        }
    except Exception:
        return {"brand": None, "model_number": None, "error_code": None}


def draft_escalation(case_id: str, store) -> dict | None:
    """Generate a drafted escalation email for the case and persist it in the store."""
    case = store.load_case(case_id)
    if not case:
        return None

    brand = case.get("brand") or "Unknown"
    brand_key = brand.upper()
    recipient = SUPPORT_CONTACTS.get(brand_key, "support@appliance-repair.com")
    
    model = case.get("model_number") or "Unknown Model"
    appliance = case.get("appliance") or "appliance"
    
    subject = f"Service Request: Troubleshooting Escalation for {brand} {model} {appliance}"
    
    recap_text = store.recap(case_id)
    
    body = (
        f"Hello Customer Support,\n\n"
        f"I am writing to request repair service for my {brand} {appliance}. "
        f"Troubleshooting steps have been exhausted without resolving the issue. "
        f"Below is the complete case history of symptoms and attempted checks:\n\n"
        f"{recap_text}\n\n"
        f"Please let me know the next steps to schedule a service visit.\n\n"
        f"Thank you."
    )

    escalation_data = {
        "drafted_email": body,
        "recipient": recipient,
        "sent": False
    }

    # Save to the CaseStore
    store.save_case(case_id, escalation=escalation_data, status="escalated")
    
    return {
        "recipient": recipient,
        "subject": subject,
        "body": body
    }
