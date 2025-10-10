"""
Convert .pth (PyTorch) classification checkpoints to ONNX for VisionCare.

Usage (cmd.exe):
  C:\\...\\python.exe backend_django\\tools\\convert_to_onnx.py \
      --ckpt path\\to\\model.pth --out backend_django\\vision_app\\models\\classifier.onnx \
      --img-size 224 --classes cataracts normal other

Notes:
 - Requires torch and torchvision installed en el entorno de conversión.
 - Backbone: MobileNetV3/EfficientNet-B0 (torchvision) o un modelo compatible con salida logits.
 - Si tu ckpt guarda state_dict con claves 'model.' se intenta ajustar automáticamente.
"""
import argparse
import json
import os
from typing import List

import torch
import torch.nn as nn
import torchvision.models as models


def build_model(num_classes: int, backbone: str = "mobilenet_v3_small") -> nn.Module:
    if backbone == "mobilenet_v3_small":
        m = models.mobilenet_v3_small(weights=None)
        in_f = m.classifier[-1].in_features
        m.classifier[-1] = nn.Linear(in_f, num_classes)
        return m
    elif backbone == "efficientnet_b0":
        m = models.efficientnet_b0(weights=None)
        in_f = m.classifier[-1].in_features
        m.classifier[-1] = nn.Linear(in_f, num_classes)
        return m
    else:
        raise ValueError(f"Backbone no soportado: {backbone}")


def load_checkpoint(model: nn.Module, ckpt_path: str) -> None:
    ckpt = torch.load(ckpt_path, map_location="cpu")
    if isinstance(ckpt, dict) and "state_dict" in ckpt:
        sd = ckpt["state_dict"]
    else:
        sd = ckpt
    # Quitar prefijos comunes
    cleaned = {}
    for k, v in sd.items():
        if k.startswith("model."):
            cleaned[k[len("model."):]] = v
        elif k.startswith("module."):
            cleaned[k[len("module."):]] = v
        else:
            cleaned[k] = v
    model.load_state_dict(cleaned, strict=False)


def export_onnx(model: nn.Module, out_path: str, img_size: int) -> None:
    model.eval()
    dummy = torch.randn(1, 3, img_size, img_size, device="cpu")
    torch.onnx.export(
        model,
        dummy,
        out_path,
        input_names=["input"],
        output_names=["logits"],
        opset_version=13,
        dynamic_axes={"input": {0: "batch"}, "logits": {0: "batch"}},
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", required=True, help="Ruta al checkpoint .pth")
    ap.add_argument("--out", required=True, help="Ruta de salida .onnx")
    ap.add_argument("--img-size", type=int, default=224)
    ap.add_argument("--backbone", type=str, default="mobilenet_v3_small", choices=["mobilenet_v3_small", "efficientnet_b0"])
    ap.add_argument("--classes", nargs='+', required=True, help="Lista de clases en el orden de salida del modelo")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    model = build_model(num_classes=len(args.classes), backbone=args.backbone)
    load_checkpoint(model, args.ckpt)
    export_onnx(model, args.out, args.img_size)

    # Save metadata JSON alongside ONNX
    meta = {
        "classes": args.classes,
        "img_size": args.img_size,
        "backbone": args.backbone,
        "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]},
    }
    with open(args.out + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"Exportado ONNX: {args.out}")
    print(f"Metadatos: {args.out}.json")


if __name__ == "__main__":
    main()
