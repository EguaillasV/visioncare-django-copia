"""
Migra todos los archivos de backend_django/media a Supabase Storage
manteniendo la misma ruta relativa. Útil antes de eliminar la carpeta media.

Uso (PowerShell o CMD):
  venv\Scripts\python.exe tools\migrate_media_to_supabase.py --upsert

Opciones:
  --dry-run   Solo lista lo que haría, sin subir (por defecto False)
  --upsert    Permitir sobrescribir si ya existe (x-upsert=true)

Requisitos:
  - Variables en .env: SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY/ANON
  - SUPABASE_BUCKET_ORIGINALS (por defecto: eye-images)
"""

from __future__ import annotations

import os
import sys
import mimetypes
from pathlib import Path
from typing import Iterator


def iter_files(root: Path) -> Iterator[Path]:
    for p in root.rglob('*'):
        if p.is_file():
            yield p


def main() -> int:
    base_dir = Path(__file__).resolve().parents[1]  # backend_django
    media_dir = base_dir / 'media'
    if not media_dir.exists():
        print(f"No existe la carpeta: {media_dir}")
        return 0

    # Cargar entorno .env si existe
    try:
        from dotenv import load_dotenv
        load_dotenv(base_dir / '.env')
    except Exception:
        pass

    # Importar cliente Supabase
    try:
        from supabase import create_client  # type: ignore
    except Exception as e:
        print("ERROR: Supabase client no instalado. Ejecuta pip install -r requirements.txt", file=sys.stderr)
        return 1

    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    if not url or not key:
        print("ERROR: Faltan SUPABASE_URL y/o SUPABASE_SERVICE_ROLE_KEY/ANON_KEY en .env", file=sys.stderr)
        return 2

    bucket = os.getenv('SUPABASE_BUCKET_ORIGINALS', 'eye-images')

    # Flags
    args = set(a.lower() for a in sys.argv[1:])
    dry_run = ('--dry-run' in args)
    upsert = ('--upsert' in args)

    client = create_client(url, key)

    total = 0
    uploaded = 0
    skipped = 0
    errors = 0
    for f in iter_files(media_dir):
        total += 1
        rel = f.relative_to(media_dir).as_posix()  # usar / en lugar de \
        ctype, _ = mimetypes.guess_type(rel)
        ctype = ctype or 'application/octet-stream'

        if dry_run:
            print(f"[DRY] subir -> {rel}")
            continue

        try:
            with f.open('rb') as fh:
                data = fh.read()
            client.storage.from_(bucket).upload(
                path=rel,
                file=data,
                file_options={
                    'content-type': ctype,
                    'x-upsert': 'true' if upsert else 'false',
                },
            )
            uploaded += 1
            if uploaded % 25 == 0:
                print(f"Subidos {uploaded}/{total}...")
        except Exception as e:
            errors += 1
            print(f"ERROR subiendo {rel}: {e}")

    print("\nResumen migración")
    print("Total encontrados:", total)
    print("Subidos:", uploaded)
    print("Saltados:", skipped)
    print("Errores:", errors)
    return 0 if errors == 0 else 3


if __name__ == '__main__':
    raise SystemExit(main())
