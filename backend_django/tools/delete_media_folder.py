"""
Elimina de forma segura la carpeta backend_django/media después de migrar a Supabase.

Uso (PowerShell o CMD):
  venv\Scripts\python.exe tools\delete_media_folder.py

Incluye confirmación interactiva si se ejecuta en terminal.
"""

from __future__ import annotations

import os
import sys
import argparse
from pathlib import Path


def remove_dir(root: Path) -> int:
    removed = 0
    for p in sorted(root.rglob('*'), reverse=True):
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
                removed += 1
            elif p.is_dir():
                p.rmdir()
        except Exception:
            pass
    try:
        root.rmdir()
    except Exception:
        pass
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=(
        "Elimina de forma segura la carpeta backend_django/media después de migrar a Supabase."
    ))
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Omitir confirmación interactiva"
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parents[1]  # backend_django
    media_dir = base_dir / 'media'

    if not media_dir.exists():
        print(f"No existe la carpeta: {media_dir}")
        return 0

    # Confirmación en modo interactivo
    if not args.yes and sys.stdin.isatty():
        resp = input(f"¿Eliminar definitivamente '{media_dir}'? (sí/no): ").strip().lower()
        if resp not in {'si', 'sí', 's', 'yes', 'y'}:
            print('Cancelado.')
            return 1

    count = remove_dir(media_dir)
    print(f"Carpeta eliminada. Archivos borrados: {count}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
