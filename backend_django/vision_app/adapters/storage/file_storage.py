from __future__ import annotations

import io
import os
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
from PIL import Image
from django.conf import settings

from ...application.ports.storage import FileStorage


class MediaFileStorage(FileStorage):
	"""Save processed previews on local MEDIA_ROOT and return absolute URL.

	Path: eye_images/processed/YYYY/MM/<uuid>.jpg
	"""

	def save_processed_preview(self, image_rgb: np.ndarray) -> Optional[str]:
		try:
			# Ensure MEDIA_ROOT exists
			media_root = getattr(settings, 'MEDIA_ROOT', None)
			media_url = getattr(settings, 'MEDIA_URL', '/media/')
			if not media_root:
				return None
			now = datetime.utcnow()
			rel_dir = os.path.join('eye_images', 'processed', f"{now.year:04d}", f"{now.month:02d}")
			abs_dir = os.path.join(media_root, rel_dir)
			os.makedirs(abs_dir, exist_ok=True)

			# Encode as JPEG
			img = Image.fromarray(image_rgb.astype(np.uint8))
			buf = io.BytesIO()
			img.save(buf, format='JPEG', quality=90)
			buf.seek(0)

			name = f"{uuid.uuid4().hex}.jpg"
			rel_path = os.path.join(rel_dir, name).replace('\\', '/')
			abs_path = os.path.join(abs_dir, name)
			with open(abs_path, 'wb') as f:
				f.write(buf.read())

			# Build absolute-ish URL (best-effort)
			base = str(media_url or '/media/')
			if not base.endswith('/'):
				base += '/'
			return base + rel_path
		except Exception:
			return None
