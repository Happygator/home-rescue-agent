from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


Status = Literal["intake", "diagnosing", "awaiting_user", "escalated", "resolved"]
StepOutcome = Literal["resolved", "not_resolved", "unsure", "skipped", "pending"]
MediaKind = Literal["plate", "symptom", "inspection_video"]


class Diagnosis(BaseModel):
    hypothesis: str
    confidence: str


class Step(BaseModel):
    step_id: int
    instruction: str
    outcome: StepOutcome
    user_result: Optional[str] = None


class MediaRef(BaseModel):
    kind: MediaKind
    ref: str
    mime: str
    taken_at: Optional[str] = None


class InspectionShot(BaseModel):
    shot_no: int
    what_to_film: str
    where: str
    narration: str


class Packet(BaseModel):
    summary: str
    model: Optional[str] = None
    error_code: Optional[str] = None
    steps_tried: int
    video_ref: Optional[str] = None
    shots_captured: int = 0
    shots_total: int = 0
    warranty_status: Optional[str] = None


class Escalation(BaseModel):
    recipient: str
    drafted_email: str
    inspection_guide: list[InspectionShot] = Field(default_factory=list)
    packet: Optional[Packet] = None
    sent: bool = False


class IssueSummary(BaseModel):
    case_id: str
    title: str
    brand: Optional[str] = None
    appliance: Optional[str] = None
    model_number: Optional[str] = None
    status: Status
    symptom: str = ""
    next_step: str = ""
    updated_at: str


class IssueDetail(BaseModel):
    case_id: str
    title: str
    brand: Optional[str] = None
    appliance: Optional[str] = None
    model_number: Optional[str] = None
    status: Status
    symptom: str = ""
    error_code: Optional[str] = None
    diagnosis: Optional[Diagnosis] = None
    steps: list[Step] = Field(default_factory=list)
    next_step: str = ""
    media: list[MediaRef] = Field(default_factory=list)
    escalation: Optional[Escalation] = None
    created_at: str
    updated_at: str


class CreateIssueRequest(BaseModel):
    appliance: Optional[str] = "Refrigerator"
    brand: Optional[str] = None
    model_number: Optional[str] = None
    symptom: Optional[str] = None
    error_code: Optional[str] = None
    user_id: Optional[str] = "user-default"


class CreateIssueResponse(BaseModel):
    case_id: str


class PlateRequest(BaseModel):
    media_ref: Optional[str] = None


class PlateResponse(BaseModel):
    brand: Optional[str] = None
    model: Optional[str] = None
    error_code: Optional[str] = None


class MediaResponse(BaseModel):
    ref: str


class MessageRequest(BaseModel):
    text: str


class EscalateResponse(BaseModel):
    drafted_email: str
    inspection_guide: list[InspectionShot]
    packet: Packet


class ResolveResponse(BaseModel):
    case_id: str
    status: Status
