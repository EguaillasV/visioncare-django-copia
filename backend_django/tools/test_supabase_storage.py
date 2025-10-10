#!/usr/bin/env python
"""
Quick Supabase Storage health check for VisionCare.

Usage (from backend_django):
  python tools/test_supabase_storage.py

Requires env vars:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY
  SUPABASE_BUCKET_PREVIEWS (default: eye-previews)
  SUPABASE_BUCKET_ORIGINALS (default: eye-images)

Optional:
  SUPABASE_SIGNED_URL_EXPIRES (seconds) for signed URLs
"""
import os
from pathlib import Path
try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None
import sys
import uuid
from io import BytesIO


def _load_client():
    # Ensure we load env vars from backend_django/.env when running directly
    if load_dotenv is not None:
        base_dir = Path(__file__).resolve().parents[1]
        env_path = base_dir / '.env'
        if env_path.exists():
            load_dotenv(env_path)
    try:
        from supabase import create_client  # type: ignore
    except Exception as e:
        print("❌ Supabase client not installed. Please install requirements.")
        raise
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/ANON_KEY")
    return create_client(url, key)


def test_bucket(client, bucket: str) -> bool:
    ok = True
    print(f"\n🔎 Testing bucket: {bucket}")
    name = f"health/{uuid.uuid4().hex}.txt"
    data = b"visioncare health check"
    try:
        client.storage.from_(bucket).upload(path=name, file=data, file_options={"content-type": "text/plain", "x-upsert": "false"})
        print("✅ Upload ok")
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return False
    try:
        pub = client.storage.from_(bucket).get_public_url(name)
        url = None
        if isinstance(pub, dict) and pub.get('data') and pub['data'].get('publicUrl'):
            url = pub['data']['publicUrl']
        else:
            base = os.getenv('SUPABASE_URL', '').rstrip('/')
            url = f"{base}/storage/v1/object/public/{bucket}/{name}"
        print(f"🌐 Public URL (if bucket is public): {url}")

        # If signed URLs desired (likely for originals/private bucket), try to create one
        signed_expires = int(os.getenv('SUPABASE_SIGNED_URL_EXPIRES', '0') or '0')
        if signed_expires > 0:
            try:
                signed = client.storage.from_(bucket).create_signed_url(name, signed_expires)
                if isinstance(signed, dict) and signed.get('signedURL'):
                    print(f"🔐 Signed URL ({signed_expires}s): {signed['signedURL']}")
            except Exception as se:
                print(f"⚠️  Could not create signed URL: {se}")
    except Exception as e:
        print(f"⚠️  Could not build public/signed URL: {e}")
        ok = False
    # Cleanup
    try:
        client.storage.from_(bucket).remove([name])
        print("🧹 Cleanup ok")
    except Exception as e:
        print(f"⚠️  Cleanup failed: {e}")
    return ok


def main():
    try:
        client = _load_client()
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    prev = os.getenv('SUPABASE_BUCKET_PREVIEWS', 'eye-previews')
    orig = os.getenv('SUPABASE_BUCKET_ORIGINALS', 'eye-images')

    ok1 = test_bucket(client, prev)
    ok2 = test_bucket(client, orig)
    if ok1 and ok2:
        print("\n🎉 Supabase Storage health check passed.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check bucket names and permissions.")
        sys.exit(2)


if __name__ == '__main__':
    main()
