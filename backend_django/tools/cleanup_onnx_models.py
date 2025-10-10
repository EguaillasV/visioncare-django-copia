import os
from glob import glob

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    onnx_dir = os.path.normpath(os.path.join(here, '..', 'vision_app', 'onnx_models'))
    patterns = ["*.pth", "*.pt", "*.pth.tar"]
    removed = []
    for pat in patterns:
        for p in glob(os.path.join(onnx_dir, pat)):
            try:
                os.remove(p)
                removed.append(os.path.basename(p))
            except Exception as e:
                print(f"No se pudo borrar {p}: {e}")
    if removed:
        print("Eliminados:", ", ".join(removed))
    else:
        print("No se encontraron archivos .pth/.pt para eliminar.")

if __name__ == "__main__":
    main()
