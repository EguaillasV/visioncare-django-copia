import os
import sys
from pathlib import Path


def safe_unlink(path: Path):
    try:
        if path.exists():
            path.unlink()
            return True
    except Exception:
        pass
    return False


def safe_rmdir(path: Path):
    try:
        if path.exists() and path.is_dir():
            # Remove all children first
            for p in path.rglob('*'):
                if p.is_file():
                    try:
                        p.unlink()
                    except Exception:
                        pass
                elif p.is_dir():
                    try:
                        p.rmdir()
                    except Exception:
                        pass
            path.rmdir()
            return True
    except Exception:
        pass
    return False


def main():
    # Starting points
    backend_dir = Path(__file__).resolve().parents[1]  # .../backend_django
    project_root = backend_dir.parent  # .../VISIONCARE_WEB
    repo_root = project_root.parent  # .../VISIONCARE-WEB

    deleted = []

    # 1) Delete debug logs
    for p in [repo_root / 'debug.log', backend_dir / 'debug.log']:
        if safe_unlink(p):
            deleted.append(str(p))

    # 2) Delete Python caches and *.pyc under backend_django
    for pyc in backend_dir.rglob('*.pyc'):
        if safe_unlink(pyc):
            deleted.append(str(pyc))
    for d in backend_dir.rglob('__pycache__'):
        # try to remove directory recursively
        if safe_rmdir(d):
            deleted.append(str(d))

    # 3) Remove old checkpoints from onnx_models (keep .onnx and .json)
    onnx_dir = backend_dir / 'vision_app' / 'onnx_models'
    for pat in ('*.pth', '*.pt', '*.ckpt', '*.pth.tar'):
        for f in onnx_dir.glob(pat):
            if safe_unlink(f):
                deleted.append(str(f))

    # 4) Media directory is preserved (user uploads). No sqlite db in this setup.
    media_path = backend_dir / 'media'

    print('Cleanup completed.')
    print('Deleted items count:', len(deleted))
    if deleted:
        print('Sample deleted:', deleted[:10])
    print('Preserved:')
    print('-', media_path, 'exists' if media_path.exists() else 'missing')


if __name__ == '__main__':
    sys.exit(main())
