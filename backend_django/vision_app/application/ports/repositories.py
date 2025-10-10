from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any, Dict, Optional


@dataclass
class AnalysisCreate:
    user_id: int
    image_file: Any 
    diagnosis: str
    severity: str
    confidence_score: float
    opencv_redness_score: float
    opencv_opacity_score: float
    opencv_vascular_density: float
    ai_analysis_text: str
    ai_confidence: float
    ai_raw_response: Dict[str, Any]
    recommendations: str
    medical_advice: str
    analysis_duration: float


class AnalysisRepo(Protocol):
    def create(self, payload: AnalysisCreate) -> Any: 
        ...


class UserRepo(Protocol):
    def get_email(self, user_id: int) -> Optional[str]:
        ...
