from __future__ import annotations

import io
import os
from typing import Optional

from django.core.files.storage import Storage
from django.core.files.base import ContentFile, File

from .supabase_common import create_supabase_client, get_public_url, create_signed_url

# Simple in-process cache for signed URLs to avoid generating them on every request
_signed_url_cache: dict[str, tuple[str, float]] = {}


class SupabaseDjangoStorage(Storage):
	"""Minimal Django Storage backend that writes to Supabase Storage.

	Bucket: VC_ORIGINALS_BUCKET or 'eye-images'
	"""

	def __init__(self, bucket: Optional[str] = None):
		# Allow both VC_* and SUPABASE_* env names; default to 'eye-images'
		self.bucket = bucket or os.getenv('VC_ORIGINALS_BUCKET') or os.getenv('SUPABASE_BUCKET_ORIGINALS') or 'eye-images'
		self.client = None  # lazy init

	def _client(self):
		if self.client is None:
			self.client = create_supabase_client()
		return self.client

	def _save(self, name: str, content: File) -> str:  # type: ignore[override]
		# Normalize path to forward slashes
		path = name.replace('\\', '/')
		data = content.read()
		# Evitar pasar booleanos crudos en opciones que se transforman en headers en supabase-py/httpx
		content_type = getattr(content, 'content_type', None) or 'application/octet-stream'
		self._client().storage.from_(self.bucket).upload(path, data, {
			'upsert': 'true',
			'contentType': str(content_type),
		})
		return path

	def save(self, name: str, content: File, max_length: Optional[int] = None) -> str:  # type: ignore[override]
		return self._save(name, content)

	def exists(self, name: str) -> bool:  # type: ignore[override]
		try:
			# list the specific path parent and check
			path = name.replace('\\', '/')
			parent = '/'.join(path.split('/')[:-1])
			res = self._client().storage.from_(self.bucket).list(parent or '')
			items = res.get('data') if isinstance(res, dict) else res
			if isinstance(items, list):
				for it in items:
					if isinstance(it, dict) and it.get('name') == os.path.basename(path):
						return True
		except Exception:
			pass
		return False

	def url(self, name: str) -> str:  # type: ignore[override]
		path = name.replace('\\', '/')
		# Prefer signed URL if configured
		try:
			# Support both VC_* and SUPABASE_* expiration envs
			expires = int(os.getenv('VC_SIGNED_URL_EXPIRES') or os.getenv('SUPABASE_SIGNED_URL_EXPIRES') or '0')
		except Exception:
			expires = 0
		if expires > 0:
			# Return cached signed URL if still valid (with a small safety margin)
			import time
			key = f"{self.bucket}:{path}:{expires}"
			entry = _signed_url_cache.get(key)
			if entry and time.time() < entry[1]:
				return entry[0]
			s = create_signed_url(self._client(), self.bucket, path, expires)
			if s:
				_ttl = max(0, expires - 5)
				_signed_url_cache[key] = (s, time.time() + _ttl)
				return s
		pub = get_public_url(self._client(), self.bucket, path)
		if pub:
			return pub
		# Fallback to a plausible public path
		base = os.getenv('SUPABASE_URL', '').rstrip('/')
		return f"{base}/storage/v1/object/public/{self.bucket}/{path}"

	# Optional: no-op implementations
	def delete(self, name: str) -> None:  # type: ignore[override]
		try:
			self._client().storage.from_(self.bucket).remove([name.replace('\\', '/')])
		except Exception:
			pass

	def size(self, name: str) -> int:  # type: ignore[override]
		return 0

	def open(self, name: str, mode: str = 'rb') -> File:  # type: ignore[override]
		# Not required for our flows; raising makes misuse obvious.
		raise NotImplementedError("Open is not supported for SupabaseDjangoStorage")
