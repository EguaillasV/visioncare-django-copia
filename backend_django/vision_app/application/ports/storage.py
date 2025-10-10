from __future__ import annotations

from typing import Protocol, Optional
import numpy as np


class FileStorage(Protocol):
    def save_processed_preview(self, image_rgb: np.ndarray) -> Optional[str]:
        """Save a processed preview image and return an absolute URL if possible."""
        ...
