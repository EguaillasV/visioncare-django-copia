"""
Deprecated module.

This file existed temporarily as a compatibility shim during the
Hexagonal refactor. The use case now lives under:

	vision_app.application.use_cases.upload_and_analyze_image

Import from the application path instead of this legacy module.
"""

raise ImportError(
		"Use 'vision_app.application.use_cases.upload_and_analyze_image' instead of 'vision_app.use_cases.upload_and_analyze_image'"
)
