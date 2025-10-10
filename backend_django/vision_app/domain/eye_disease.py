"""Domain entities and value objects facade.

Currently delegates to image_processing metrics as domain primitives.
"""

from .image_processing import (
    analyze_eye_features,
    enhance_image_quality,
    detect_eye_region,
    compute_image_quality,
)
