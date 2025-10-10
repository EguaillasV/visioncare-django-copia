from __future__ import annotations

import io
import os
import uuid
from datetime import datetime
from typing import Optional

import numpy as np
from PIL import Image

from .supabase_common import create_supabase_client, get_public_url
from ...application.ports.storage import FileStorage


class SupabaseFileStorage(FileStorage):
	"""Upload processed previews to Supabase Storage and return a public URL.

	Bucket default: VC_PREVIEWS_BUCKET or 'eye-previews'
	Path: processed/YYYY/MM/<uuid>.jpg
	"""

	def __init__(self, bucket: Optional[str] = None):
		self.bucket = bucket or os.getenv('VC_PREVIEWS_BUCKET', 'eye-previews')

	def save_processed_preview(self, image_rgb: np.ndarray) -> Optional[str]:
		try:
			client = create_supabase_client()
			# Encode image to JPEG
			img = Image.fromarray(image_rgb.astype(np.uint8))
			buf = io.BytesIO()
			img.save(buf, format='JPEG', quality=90)
			buf.seek(0)
			now = datetime.utcnow()
			path = f"processed/{now.year:04d}/{now.month:02d}/{uuid.uuid4().hex}.jpg"
			# Nota: algunas versiones de supabase-py/httpx esperan headers stringificados;
			# usar 'upsert': 'false' evita errores del tipo "'bool' object has no attribute 'encode'".
			client.storage.from_(self.bucket).upload(path, buf.getvalue(), {
				'contentType': 'image/jpeg',
				'upsert': 'false',
			})
			url = get_public_url(client, self.bucket, path)
			return url
		except Exception:
			return None
