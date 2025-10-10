#!/usr/bin/env python3
"""
Create or update Supabase Storage buckets for VisionCare.
- Originals bucket (default: eye-images)
- Previews bucket (default: eye-previews)

Uses SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) from backend_django/.env

Usage examples (Windows cmd):
  python tools\create_supabase_buckets.py --previews-public --originals-private
  python tools\create_supabase_buckets.py --list

Notes:
- "public=True" on a bucket allows public read access via /storage/v1/object/public/... URLs
- For private buckets, you'll need signed URLs (SUPABASE_SIGNED_URL_EXPIRES) or authenticated access.
"""
import os
import sys
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore
except Exception:
    load_dotenv = None


def load_env(env_path: Path) -> None:
    # Load .env next to manage.py (backend_django/.env)
    if load_dotenv is not None and env_path.exists():
        load_dotenv(env_path)


def coerce_bucket_list(buckets):
    # supabase-py v2 returns list of dict-like objects
    result = []
    for b in (buckets or []):
        # handle dict or object with attributes
        name = b.get("name") if isinstance(b, dict) else getattr(b, "name", None)
        public = b.get("public") if isinstance(b, dict) else getattr(b, "public", None)
        result.append({"name": name, "public": public})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Create/Update Supabase Storage buckets")
    parser.add_argument("--originals", default=os.getenv("SUPABASE_BUCKET_ORIGINALS", "eye-images"))
    parser.add_argument("--previews", default=os.getenv("SUPABASE_BUCKET_PREVIEWS", "eye-previews"))
    parser.add_argument("--originals-public", action="store_true", help="Make originals bucket public (default private)")
    parser.add_argument("--originals-private", action="store_true", help="Make originals bucket private (default)")
    parser.add_argument("--previews-public", action="store_true", help="Make previews bucket public (default public)")
    parser.add_argument("--previews-private", action="store_true", help="Make previews bucket private")
    parser.add_argument("--list", action="store_true", help="List buckets and exit")

    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parents[1]
    env_path = base_dir / ".env"
    load_env(env_path)

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY/ANON_KEY are required in backend_django/.env")
        return 1

    try:
        from supabase import create_client  # type: ignore
    except Exception as e:
        print("ERROR: supabase package not installed. Add 'supabase' to backend_django/requirements.txt and install.")
        print(str(e))
        return 1

    client = create_client(url, key)

    # Helper to ensure bucket state
    def ensure_bucket(name: str, public: bool):
        existing = coerce_bucket_list(client.storage.list_buckets())
        names = {b["name"]: b for b in existing}
        if name in names:
            current_public = bool(names[name].get("public"))
            if current_public != public:
                print(f"Updating bucket '{name}' public={public} (was {current_public})...")
                client.storage.update_bucket(name, public=public)
            else:
                print(f"Bucket '{name}' already exists with public={current_public}")
        else:
            print(f"Creating bucket '{name}' public={public}...")
            client.storage.create_bucket(name, public=public)

    if args.list:
        buckets = coerce_bucket_list(client.storage.list_buckets())
        if not buckets:
            print("No buckets found.")
        else:
            for b in buckets:
                print(f"- {b['name']} (public={b['public']})")
        return 0

    # Resolve desired public flags
    originals_public = False
    if args.originals_public:
        originals_public = True
    if args.originals_private:
        originals_public = False

    previews_public = True
    if args.previews_private:
        previews_public = False
    if args.previews_public:
        previews_public = True

    # Apply
    ensure_bucket(args.originals, originals_public)
    ensure_bucket(args.previews, previews_public)

    # Show helpful URLs
    base = url.rstrip('/')
    print("\nHelpful URLs (if buckets are public):")
    print(f"  Originals: {base}/storage/v1/object/public/{args.originals}/<path/to/file>")
    print(f"  Previews:  {base}/storage/v1/object/public/{args.previews}/<path/to/file>")

    # Signed URL note
    print("\nIf Originals is private, set SUPABASE_SIGNED_URL_EXPIRES in .env to enable signed URLs in Django storage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
