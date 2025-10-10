Place your ONNX models here.

Recommended convention:
- classifier.onnx (+ classifier.onnx.json metadata)
- Or set environment variables:
  - VC_ONNX_MODEL=absolute\or\relative\path\to\model.onnx
  - VC_ONNX_MODELS=path1.onnx;path2.onnx (for simple ensemble averaging)

Metadata sidecar JSON (optional but recommended):
{
  "classes": ["normal", "cataracts", "other"],
  "img_size": 224,
  "backbone": "mobilenet_v3_small",
  "normalization": {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]}
}

Conversion script:
Use backend_django/tools/convert_to_onnx.py to convert .pth to .onnx.
