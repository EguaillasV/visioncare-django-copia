from __future__ import annotations

from typing import Dict, Any, Optional, Protocol
import numpy as np


class EyeDiseaseDetector(Protocol):
    def infer_probs(self, image_rgb: np.ndarray) -> Optional[Dict[str, float]]:
        """Return class->prob dict or None if model unavailable."""
        ...

    def infer_tta(self, image_rgb: np.ndarray) -> Optional[Dict[str, Any]]:
        """Return dict with 'probs' and 'uncertainty' keys when available."""
        ...
