"""Domain models and Pydantic schemas for loans."""

from typing import Any, Dict, List, Optional
import json
from pydantic import BaseModel, Field, ConfigDict, model_validator

class FieldMetadata(BaseModel):
    """Metadata detailing OCR extraction confidence and edit status per field."""
    value: Any = None
    confidence: float = 0.0  # Normalized between 0.00 and 1.00
    is_low_confidence: bool = False  # True if confidence < CONFIDENCE_THRESHOLD (0.80)
    engine: str = "unknown"
    manually_edited: bool = False
    bounding_box: Optional[Dict[str, Any]] = None

class LoanBase(BaseModel):
    """Base schema for loan data."""
    serial_number: str
    name: str
    mobile: str
    address: Optional[str] = ""
    amount: float
    batch_id: Optional[str] = None
    row_index: Optional[int] = None
    project_type: str = "loan"

class LoanCreate(LoanBase):
    """Payload for creating a new loan record (e.g. from OCR extraction)."""
    image_path: Optional[str] = None
    raw_ocr_data: Optional[Dict[str, Any]] = None
    confidences: Dict[str, float] = Field(default_factory=dict)
    ocr_engine_used: str = "gcp_vision"
    verified: bool = False
    verified_at: Optional[str] = None

class LoanUpdate(BaseModel):
    """Payload for updating loan fields."""
    serial_number: Optional[str] = None
    name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    amount: Optional[float] = None
    batch_id: Optional[str] = None
    row_index: Optional[int] = None
    verified: Optional[bool] = None
    verified_at: Optional[str] = None
    confidences: Optional[Dict[str, float]] = None

class VerificationPayload(BaseModel):
    """User-submitted verification payload from HITL split-screen UI."""
    serial_number: Optional[str] = None
    name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    amount: Optional[float] = None

class BatchVerificationRow(BaseModel):
    """Schema for individual row within batch verification payload."""
    model_config = ConfigDict(extra="allow")

    id: Optional[int] = None
    loan_id: Optional[int] = None
    row_index: Optional[int] = None
    project_type: Optional[str] = "loan"
    serial_number: Optional[str] = None
    name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    amount: Optional[float] = None
    confidences: Optional[Dict[str, float]] = None
    is_low_confidence: Optional[bool] = None
    manually_edited: Optional[bool] = None

class BatchVerificationRequest(BaseModel):
    """Payload for submitting verified batch grid."""
    batch_id: str
    project_type: str = "loan"
    records: List[Dict[str, Any]] = Field(default_factory=list)
    rows: Optional[List[Dict[str, Any]]] = None
    deleted_ids: Optional[List[int]] = Field(default_factory=list)

class LoanRecord(LoanBase):
    """Complete persisted loan record representation."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_path: Optional[str] = None
    raw_ocr_data: Optional[Dict[str, Any]] = None
    confidences: Dict[str, float] = Field(default_factory=dict)
    ocr_engine_used: str
    verified: bool = False
    verified_at: Optional[str] = None
    created_at: str
    updated_at: str

    @model_validator(mode="before")
    @classmethod
    def parse_json_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Parse confidences if serialized as JSON string
            if isinstance(data.get("confidences"), str):
                try:
                    data["confidences"] = json.loads(data["confidences"])
                except Exception:
                    data["confidences"] = {}
            # Parse raw_ocr_data if serialized as JSON string
            if isinstance(data.get("raw_ocr_data"), str):
                try:
                    data["raw_ocr_data"] = json.loads(data["raw_ocr_data"])
                except Exception:
                    data["raw_ocr_data"] = None
            # Convert verified integer (0 or 1) to bool if needed
            if "verified" in data and isinstance(data["verified"], int):
                data["verified"] = bool(data["verified"])
        return data

class BatchResponse(BaseModel):
    """Batch verification or retrieval response."""
    batch_id: str
    success: bool = True
    verified_count: int = 0
    total_rows: int = 0
    records: List[LoanRecord] = Field(default_factory=list)
    image_path: Optional[str] = None

