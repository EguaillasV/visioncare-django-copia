from __future__ import annotations

from typing import Dict, Any, Optional
import numpy as np
from PIL import Image

from ...application.ports.ai_services import EyeDiseaseDetector
from ...infer import (
	infer_probs as _infer_probs,
	infer_tta as _infer_tta,
	get_runtime_info as _get_runtime_info,
)


class OnnxEyeDiseaseDetector(EyeDiseaseDetector):
	def infer_probs(self, image_rgb: np.ndarray) -> Optional[Dict[str, float]]:
		img = Image.fromarray(image_rgb)
		return _infer_probs(img)

	def infer_tta(self, image_rgb: np.ndarray) -> Optional[Dict[str, Any]]:
		img = Image.fromarray(image_rgb)
		tta = _infer_tta(img)
		# enrich with runtime info to keep parity with view
		try:
			info = _get_runtime_info()
			if isinstance(tta, dict) and isinstance(info, dict):
				tta = dict(tta)
				tta.setdefault('providers', info.get('providers'))
				tta.setdefault('class_names', info.get('class_names'))
				tta.setdefault('model_count', info.get('model_count'))
				tta.setdefault('img_size', info.get('img_size'))
		except Exception:
			pass
		return tta
