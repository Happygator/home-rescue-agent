from __future__ import annotations

import datetime

from app.models import (
    Diagnosis,
    Escalation,
    InspectionShot,
    IssueDetail,
    MediaRef,
    Packet,
    Step,
)


def _iso(dt: datetime.datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def build_seed() -> dict[str, IssueDetail]:
    now = datetime.datetime.now(datetime.timezone.utc)

    def ago(**kw: int) -> str:
        return _iso(now - datetime.timedelta(**kw))

    issues: dict[str, IssueDetail] = {}

    issues["case-7f3a9c21"] = IssueDetail(
        case_id="case-7f3a9c21",
        title="Samsung \u00b7 Refrigerator",
        brand="Samsung",
        appliance="Refrigerator",
        model_number="RF28R7201",
        status="diagnosing",
        symptom="Fresh-food warm; freezer still cold.",
        error_code=None,
        diagnosis=Diagnosis(
            hypothesis="Restricted airflow / dirty coils",
            confidence="medium",
        ),
        steps=[
            Step(
                step_id=1,
                instruction="Set temp to 37\u00b0F",
                outcome="not_resolved",
                user_result="no change",
            ),
            Step(
                step_id=2,
                instruction="Cleared vents",
                outcome="not_resolved",
                user_result="no change",
            ),
            Step(
                step_id=3,
                instruction="Clean condenser coils",
                outcome="pending",
                user_result=None,
            ),
        ],
        next_step="Confirm coils are clean, then test the evaporator fan.",
        media=[
            MediaRef(
                kind="plate",
                ref="plate-001.jpg",
                mime="image/jpeg",
                taken_at=ago(hours=2),
            )
        ],
        escalation=None,
        created_at=ago(hours=3),
        updated_at=ago(hours=2),
    )

    issues["case-2b8e1d40"] = IssueDetail(
        case_id="case-2b8e1d40",
        title="Whirlpool \u00b7 Refrigerator",
        brand="Whirlpool",
        appliance="Refrigerator",
        model_number="WRX735SDHZ",
        status="awaiting_user",
        symptom="Ice maker stopped; water still works.",
        diagnosis=Diagnosis(
            hypothesis="Frozen fill tube / water inlet",
            confidence="low",
        ),
        steps=[
            Step(
                step_id=1,
                instruction="Check the water-line shutoff valve",
                outcome="pending",
                user_result=None,
            )
        ],
        next_step="Check the water-line shutoff valve, then report back.",
        created_at=ago(days=1, hours=2),
        updated_at=ago(days=1),
    )

    issues["case-9c4f7a02"] = IssueDetail(
        case_id="case-9c4f7a02",
        title="LG \u00b7 Refrigerator",
        brand="LG",
        appliance="Refrigerator",
        model_number="LFXS26973S",
        status="escalated",
        symptom="Compressor clicks, no cooling.",
        diagnosis=Diagnosis(
            hypothesis="Failed compressor / start relay (sealed system)",
            confidence="high",
        ),
        steps=[
            Step(
                step_id=1,
                instruction="Vacuum condenser coils",
                outcome="not_resolved",
                user_result="still warm",
            ),
            Step(
                step_id=2,
                instruction="Check start relay rattle",
                outcome="not_resolved",
                user_result="clicks repeatedly",
            ),
            Step(
                step_id=3,
                instruction="Confirm no cooling after 3h",
                outcome="not_resolved",
                user_result="confirmed",
            ),
        ],
        next_step=(
            "Pro service required - escalation email + inspection video guide ready "
            "to send."
        ),
        escalation=Escalation(
            recipient="support@lg.com",
            drafted_email=(
                "Hello LG Customer Support,\n\nI need to schedule a service visit for my LG "
                "refrigerator (model LFXS26973S). The compressor clicks repeatedly and the unit "
                "is not cooling. I have already tried: vacuuming the condenser coils, checking the "
                "start relay, and confirming no cooling after 3 hours. Please dispatch a technician.\n\n"
                "Thank you."
            ),
            inspection_guide=[
                InspectionShot(
                    shot_no=1,
                    what_to_film="The spec / model plate",
                    where="Inside the fridge, left wall",
                    narration="Read out the model number on the plate.",
                ),
                InspectionShot(
                    shot_no=2,
                    what_to_film="Frame the display panel",
                    where="Front control panel",
                    narration="Show the temperature display so the tech can read the error.",
                ),
                InspectionShot(
                    shot_no=3,
                    what_to_film="The compressor and start relay",
                    where="Lower rear access panel",
                    narration="Capture the clicking sound near the compressor.",
                ),
                InspectionShot(
                    shot_no=4,
                    what_to_film="Narrate the symptom + steps tried",
                    where="Standing at the fridge",
                    narration="Say what is wrong and what you already tried.",
                ),
            ],
            packet=Packet(
                summary=(
                    "LG refrigerator not cooling; compressor clicks. 3 steps tried, "
                    "no resolution."
                ),
                model="LFXS26973S",
                error_code=None,
                steps_tried=3,
                video_ref=None,
                shots_captured=2,
                shots_total=4,
                warranty_status="checking...",
            ),
            sent=False,
        ),
        media=[
            MediaRef(
                kind="plate",
                ref="plate-lg.jpg",
                mime="image/jpeg",
                taken_at=ago(days=3, hours=1),
            )
        ],
        created_at=ago(days=3, hours=4),
        updated_at=ago(days=3),
    )

    resolved_specs = [
        (
            "case-res-01",
            "Samsung",
            "RF28R7201",
            "Door alarm kept beeping.",
            "Door was ajar; reseated the gasket.",
        ),
        (
            "case-res-02",
            "GE",
            "GSS25",
            "Water dispenser slow.",
            "Replaced the clogged water filter.",
        ),
        (
            "case-res-03",
            "Whirlpool",
            "WRS555",
            "Freezer frosting over.",
            "Door seal cleaned; closes fully now.",
        ),
        (
            "case-res-04",
            "Frigidaire",
            "FFHB2750",
            "Demo mode OF OF on display.",
            "Exited showroom/demo mode.",
        ),
    ]
    for i, (cid, brand, model, symptom, fix) in enumerate(resolved_specs):
        issues[cid] = IssueDetail(
            case_id=cid,
            title=f"{brand} \u00b7 Refrigerator",
            brand=brand,
            appliance="Refrigerator",
            model_number=model,
            status="resolved",
            symptom=symptom,
            diagnosis=Diagnosis(hypothesis=fix, confidence="high"),
            steps=[
                Step(
                    step_id=1,
                    instruction=fix,
                    outcome="resolved",
                    user_result="fixed it",
                )
            ],
            next_step="",
            created_at=ago(days=10 + i),
            updated_at=ago(days=5 + i),
        )
    return issues
