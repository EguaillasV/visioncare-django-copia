from __future__ import annotations

import os
from typing import Optional


def create_supabase_client():
	"""Create and return a Supabase client using env vars.

	Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY.
	"""
	try:
		from supabase import create_client  # type: ignore
	except Exception as e:
		raise RuntimeError("Supabase client not installed. Add 'supabase' to requirements.") from e

	url = os.getenv('SUPABASE_URL')
	key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
	if not url or not key:
		raise RuntimeError("Missing SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY/ANON_KEY env vars")
	return create_client(url, key)


def get_public_url(client, bucket: str, path: str) -> Optional[str]:
	"""Best-effort to build a public URL for an object."""
	try:
		pub = client.storage.from_(bucket).get_public_url(path)
		# supabase-py v2 returns { 'data': { 'publicUrl': '...' } }
		if isinstance(pub, dict):
			data = pub.get('data')
			if isinstance(data, dict):
				url = data.get('publicUrl') or data.get('public_url')
				if url:
					return str(url)
	except Exception:
		pass
	base = os.getenv('SUPABASE_URL', '').rstrip('/')
	if base:
		return f"{base}/storage/v1/object/public/{bucket}/{path}"
	return None


def create_signed_url(client, bucket: str, path: str, expires: int) -> Optional[str]:
	"""Create a signed URL if supported and expires > 0.

	Handles multiple possible response shapes from supabase-py:
	- {'signedURL': '...'}
	- {'data': {'signedUrl': '...'}}
	- {'data': {'signed_url': '...'}}
	"""
	if expires and expires > 0:
		try:
			res = client.storage.from_(bucket).create_signed_url(path, expires)
			if isinstance(res, dict):
				# direct key
				if res.get('signedURL'):
					return str(res['signedURL'])
				# nested data keys
				data = res.get('data')
				if isinstance(data, dict):
					url = data.get('signedUrl') or data.get('signed_url') or data.get('signedURL')
					if url:
						return str(url)
		except Exception:
			return None
	return None
