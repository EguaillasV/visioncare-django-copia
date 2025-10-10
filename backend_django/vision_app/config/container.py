from __future__ import annotations

from ..adapters.repositories.orm_repositories import DjangoAnalysisRepo
import os
from ..adapters.storage.file_storage import MediaFileStorage
from ..adapters.storage.supabase_storage import SupabaseFileStorage
from ..adapters.ai.onnx_detector import OnnxEyeDiseaseDetector
from ..application.use_cases.upload_and_analyze_image import UploadAndAnalyzeImage


def get_analysis_use_case() -> UploadAndAnalyzeImage:
    storage_kind = (os.getenv('VC_STORAGE', 'media').strip().lower())
    if storage_kind in ('supabase', 'supabase_storage'):
        storage = SupabaseFileStorage()
    else:
        storage = MediaFileStorage()

    return UploadAndAnalyzeImage(
        repo=DjangoAnalysisRepo(),
        storage=storage,
        detector=OnnxEyeDiseaseDetector(),
    )
