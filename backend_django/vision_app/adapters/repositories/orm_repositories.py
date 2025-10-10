from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from django.core.files.base import File

from ...application.ports.repositories import AnalysisRepo, AnalysisCreate
from ...models import Analysis, User


class DjangoAnalysisRepo(AnalysisRepo):
	def create(self, payload: AnalysisCreate) -> Any:
		ts0 = time.perf_counter()
		try:
			user = User.objects.get(pk=payload.user_id)
		except Exception as e:
			raise ValueError(f"User not found: {payload.user_id}") from e

		# payload.image_file is expected to be a Django UploadedFile
		analysis = Analysis.objects.create(
			user=user,
			image=payload.image_file if isinstance(payload.image_file, File) else payload.image_file,
			diagnosis=payload.diagnosis,
			severity=payload.severity,
			confidence_score=float(payload.confidence_score),
			opencv_redness_score=float(payload.opencv_redness_score),
			opencv_opacity_score=float(payload.opencv_opacity_score),
			opencv_vascular_density=float(payload.opencv_vascular_density),
			ai_analysis_text=str(payload.ai_analysis_text),
			ai_confidence=float(payload.ai_confidence),
			ai_raw_response=dict(payload.ai_raw_response or {}),
			recommendations=str(payload.recommendations),
			medical_advice=str(payload.medical_advice),
			analysis_duration=float(payload.analysis_duration),
		)
		# Update duration if not provided
		if not payload.analysis_duration:
			try:
				dt = time.perf_counter() - ts0
				analysis.analysis_duration = float(dt)
				analysis.save(update_fields=["analysis_duration"])
			except Exception:
				pass
		return analysis
