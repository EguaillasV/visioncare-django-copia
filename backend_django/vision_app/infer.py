import os
import json
from typing import List, Any
import threading
from glob import glob
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover
    ort = None

_session_lock = threading.Lock()
_sessions: List[Any] = []
_input_names: List[str] = []
_output_names: List[str] = []
_class_names: Tuple[str, ...] = ("normal", "cataracts", "other")
_img_size: int = 224
_providers_selected: List[str] = []
_load_errors: List[Dict[str, str]] = []
_model_paths_selected: List[str] = []


def _get_model_paths() -> List[str]:
    """Resolve model paths robustly across environments (Windows-friendly).

    Priority:
    1) VC_ONNX_MODELS (semicolon-separated)
    2) VC_ONNX_MODEL (single)
    3) Auto-discover in common roots: module dir, Django BASE_DIR, CWD
    """
    # 1) If user provides a list for ensemble
    list_env = os.getenv("VC_ONNX_MODELS")
    if list_env:
        paths = [p.strip().strip('"') for p in list_env.split(";") if p.strip()]
        return paths
    # 2) Single model via env var
    single = os.getenv("VC_ONNX_MODEL")
    if single:
        return [single]

    # 3) Auto-discover across likely roots
    candidates: List[str] = []
    module_dir = os.path.dirname(__file__)
    roots = [
        module_dir,
        os.path.dirname(module_dir),  # backend_django
        os.getcwd(),
    ]
    # Try Django BASE_DIR if available
    try:
        from django.conf import settings as dj_settings  # type: ignore
        base_dir = getattr(dj_settings, 'BASE_DIR', None)
        if base_dir and isinstance(base_dir, (str, os.PathLike)):
            roots.append(str(base_dir))
    except Exception:
        pass

    seen = set()
    def add_path(p: str):
        ap = os.path.abspath(p)
        if ap not in seen and os.path.exists(ap):
            seen.add(ap)
            candidates.append(ap)

    # Search patterns under each root
    for r in roots:
        # Typical location: <root>/vision_app/onnx_models/*.onnx or <module_dir>/onnx_models/*.onnx
        paths = glob(os.path.join(r, "vision_app", "onnx_models", "*.onnx"))
        for p in paths:
            add_path(p)
        paths2 = glob(os.path.join(r, "onnx_models", "*.onnx"))
        for p in paths2:
            add_path(p)

    # If still empty, try known filenames in the module's onnx_models
    fallback_dir = os.path.join(module_dir, "onnx_models")
    for name in (
        "EyeCataractDetectModel.onnx",
        "MultipleEyeDiseaseDetectModel.onnx",
        "classifier.onnx",
    ):
        p = os.path.join(fallback_dir, name)
        if os.path.exists(p):
            add_path(p)

    return sorted(candidates)


def _get_weights(n: int) -> np.ndarray:
    """Read VC_ONNX_WEIGHTS env as semicolon-separated floats. Fallback to uniform.
    If count mismatches or invalid, returns uniform weights.
    """
    ws = os.getenv("VC_ONNX_WEIGHTS")
    if not ws:
        # Optional bias toward EyeCataractDetectModel when 2 models are present
        try:
            bias_flag = str(os.getenv("VC_BIAS_CAT", "1")).strip().lower() not in ("0", "false", "no", "")
        except Exception:
            bias_flag = True
        if bias_flag and n == 2 and _model_paths_selected:
            # Give higher weight to the EyeCataractDetectModel if present
            idx_cataract = None
            for i, p in enumerate(_model_paths_selected[:2]):
                name = os.path.basename(p).lower()
                if "eyecataract" in name or "cataract" in name:
                    idx_cataract = i
                    break
            if idx_cataract is not None:
                w = np.array([0.4, 0.6], dtype=np.float32)
                if idx_cataract == 0:
                    w = np.array([0.6, 0.4], dtype=np.float32)
                return w
        return np.ones((n,), dtype=np.float32) / float(n if n > 0 else 1)
    try:
        parts = [p.strip() for p in ws.split(";") if p.strip()]
        vals = np.array([float(x) for x in parts], dtype=np.float32)
        if len(vals) != n or np.sum(vals) == 0:
            return np.ones((n,), dtype=np.float32) / float(n if n > 0 else 1)
        vals = vals / np.sum(vals)
        return vals
    except Exception:
        return np.ones((n,), dtype=np.float32) / float(n if n > 0 else 1)


def _resolve_providers() -> List[str]:
    """Resolve preferred ONNX Runtime providers based on availability and env.

    Order of preference (Windows): CUDA > DirectML > OpenVINO > CPU
    Users can override via VC_ORT_PROVIDERS (semicolon-separated)
    """
    if ort is None:
        return []

    # User override
    override = os.getenv("VC_ORT_PROVIDERS")
    if override:
        items = [p.strip() for p in override.split(";") if p.strip()]
        # Keep only available
        avail = set(ort.get_available_providers())
        return [p for p in items if p in avail]

    desired = [
        "CUDAExecutionProvider",
        "DmlExecutionProvider",  # DirectML
        "OpenVINOExecutionProvider",
        "CPUExecutionProvider",
    ]
    avail = set(ort.get_available_providers())
    return [p for p in desired if p in avail]


def load_session() -> bool:
    global _sessions, _input_names, _output_names, _class_names, _img_size, _providers_selected, _model_paths_selected
    if ort is None:
        return False
    model_paths = _get_model_paths()
    model_paths = [p for p in model_paths if p and os.path.exists(p)]
    if not model_paths:
        return False
    with _session_lock:
        if _sessions:
            return True
        _model_paths_selected = list(model_paths)
        _providers_selected = _resolve_providers()
        if not _providers_selected:
            # Fallback safe default
            _providers_selected = ["CPUExecutionProvider"]
        for mp in model_paths:
            try:
                sess = ort.InferenceSession(mp, providers=_providers_selected)  # type: ignore
                _sessions.append(sess)
                _input_names.append(sess.get_inputs()[0].name)
                _output_names.append(sess.get_outputs()[0].name)
                # Load sidecar metadata if present (use first that has it)
                meta_path = mp + ".json"
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        if isinstance(meta.get("classes"), list) and meta["classes"]:
                            _class_names = tuple(str(x) for x in meta["classes"])  # type: ignore
                        if isinstance(meta.get("img_size"), int) and meta["img_size"] > 0:
                            _img_size = int(meta["img_size"])  # type: ignore
                    except Exception:
                        pass
            except Exception as e:  # capture to debug endpoint
                try:
                    _load_errors.append({"path": mp, "error": str(e)})
                except Exception:
                    pass
    return True


def preprocess(image: Image.Image, size: Optional[int] = None) -> np.ndarray:
    if size is None:
        size = _img_size
    if image.mode != "RGB":
        image = image.convert("RGB")
    image = image.resize((size, size), Image.BILINEAR)
    arr = np.asarray(image).astype(np.float32) / 255.0
    # Normalize with ImageNet stats
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    arr = (arr - mean) / std
    arr = np.transpose(arr, (2, 0, 1))  # CHW
    arr = np.expand_dims(arr, 0)  # NCHW
    return arr


def _softmax(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Numerically-stable softmax with temperature.
    temperature < 1.0 -> sharpen; > 1.0 -> smooth
    """
    t = max(1e-6, float(temperature))
    z = logits.astype(np.float32) / t
    z = z - np.max(z)
    e = np.exp(z)
    return e / np.sum(e)


def _run_logits(inp: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Run all models and return (weighted_probs, per_model_maxprob).

    We intentionally aggregate at probability level (post-softmax) to
    preserve each model's calibration, using user-provided weights.
    """
    assert _sessions and _input_names and _output_names
    num_models = len(_sessions)
    weights = _get_weights(num_models)
    temperature_env = os.getenv("VC_TEMP")
    # Clamp temperature to a reasonable range to avoid extreme smoothing/sharpening
    if temperature_env:
        try:
            temperature = float(temperature_env)
            temperature = max(0.5, min(2.0, temperature))
        except Exception:
            temperature = 1.0
    else:
        temperature = 1.0
    agg = np.zeros((len(_class_names),), dtype=np.float32)
    maxprob_list = []
    for idx, (sess, in_name, out_name) in enumerate(zip(_sessions, _input_names, _output_names)):
        outputs = sess.run([out_name], {in_name: inp})
        logits = outputs[0].squeeze().astype(np.float32)
        probs = _softmax(logits, temperature=temperature)
        w = float(weights[idx]) if idx < len(weights) else (1.0 / float(num_models))
        agg = agg + (w * probs)
        maxprob_list.append(float(np.max(probs)))
    return agg, np.array(maxprob_list, dtype=np.float32)


def infer_probs(image: Image.Image) -> Optional[Dict[str, float]]:
    """Single-pass probability inference (ensemble-aware).

    Respects VC_TEMP for temperature scaling and VC_ONNX_* for paths/weights.
    """
    if not load_session():
        return None
    inp = preprocess(image)
    probs, _ = _run_logits(inp)
    return {cls: float(p) for cls, p in zip(_class_names, probs)}


def get_model_count() -> int:
    """Return number of ONNX models loaded (0 if none)."""
    if not load_session():
        return 0
    return len(_sessions)


def _augmentations(img: Image.Image) -> List[Image.Image]:
    """Deterministic small set of augs for TTA to reduce variance.

    We keep augs light and photometrically plausible for ocular images.
    """
    augs: List[Image.Image] = []
    augs.append(img)
    # Use very mild and photometrically plausible augs only
    try:
        augs.append(ImageOps.autocontrast(img, cutoff=1))
    except Exception:
        pass
    try:
        augs.append(ImageEnhance.Brightness(img).enhance(1.03))
    except Exception:
        pass
    # Keep TTA small (<=3) to reduce disagreement inflation
    return augs[:3]


def infer_tta(image: Image.Image) -> Optional[Dict[str, Any]]:
    """Run test-time augmentation to get mean probs and simple uncertainty.

    Returns dict with keys: probs (dict), uncertainty (dict), per_aug (list),
    providers (list), class_names (list), model_count (int)
    """
    if not load_session():
        return None
    images = _augmentations(image)
    per_aug_probs: List[np.ndarray] = []
    per_aug_top: List[float] = []
    for img_aug in images:
        inp = preprocess(img_aug)
        probs, maxprob_per_model = _run_logits(inp)
        per_aug_probs.append(probs)
        per_aug_top.append(float(np.max(probs)))
    mat = np.stack(per_aug_probs, axis=0)  # [A, C]
    mean_probs = np.mean(mat, axis=0)
    # Defensive re-normalization to ensure probabilities sum to 1
    s = float(np.sum(mean_probs))
    if not np.isfinite(s) or s <= 0:
        mean_probs = np.ones_like(mean_probs, dtype=np.float32) / float(len(mean_probs) or 1)
    else:
        mean_probs = mean_probs / s
    std_probs = np.std(mat, axis=0)
    # Predictive entropy as uncertainty (higher => more uncertain)
    eps = 1e-8
    entropy = float(-np.sum(mean_probs * np.log(mean_probs + eps)))
    class_count = int(len(_class_names)) if _class_names else 0
    max_entropy = float(np.log(max(2, class_count))) if class_count else 1.0
    entropy_norm = float(entropy / max_entropy) if max_entropy > 0 else 0.0
    # clamp to [0,1] to be safe
    entropy_norm = float(max(0.0, min(1.0, entropy_norm)))
    # Also report mean top-prob across augs (higher => more certain)
    mean_top = float(np.mean(per_aug_top))
    std_top = float(np.std(per_aug_top)) if len(per_aug_top) > 1 else 0.0
    result = {
        "probs": {cls: float(p) for cls, p in zip(_class_names, mean_probs)},
        "uncertainty": {
            "entropy": entropy,
            "entropy_normalized": entropy_norm,
            "max_entropy": max_entropy,
            "class_count": class_count,
            "n_augs": int(len(images)),
            "per_class_std": {cls: float(s) for cls, s in zip(_class_names, std_probs)},
            "mean_top_prob": mean_top,
            "std_top_prob": std_top,
        },
        "per_aug": [
            {cls: float(p) for cls, p in zip(_class_names, row)} for row in per_aug_probs
        ],
        "providers": list(_providers_selected),
        "class_names": list(_class_names),
        "model_count": get_model_count(),
    }
    return result


def get_runtime_info() -> Dict[str, Any]:
    """Expose runtime metadata useful for debugging and UI badges."""
    if not load_session():
        return {
            "loaded": False,
            "providers": [],
            "class_names": list(_class_names),
            "model_count": 0,
            "img_size": _img_size,
        }
    return {
        "loaded": True,
        "providers": list(_providers_selected),
        "class_names": list(_class_names),
        "model_count": get_model_count(),
        "img_size": _img_size,
    }


def get_runtime_debug() -> Dict[str, Any]:
    """Return extended debug info: paths, envs, providers availability."""
    info: Dict[str, Any] = {}
    try:
        cwd = os.getcwd()
        base_dir = os.path.dirname(__file__)
        onnx_dir = os.path.join(base_dir, "onnx_models")
        import sys  # local import to report runtime env
        # Candidates from resolution logic
        candidates = _get_model_paths()
        paths = []
        for p in candidates:
            paths.append({"path": p, "exists": bool(p and os.path.exists(p))})
        info.update({
            "cwd": cwd,
            "module_dir": base_dir,
            "onnx_dir": onnx_dir,
            "python_executable": sys.executable,
            "python_version": sys.version,
            "sys_path_head": sys.path[:5],
            "candidates": paths,
            "env": {
                "VC_ONNX_MODELS": os.getenv("VC_ONNX_MODELS"),
                "VC_ONNX_MODEL": os.getenv("VC_ONNX_MODEL"),
                "VC_ORT_PROVIDERS": os.getenv("VC_ORT_PROVIDERS"),
                "VC_TEMP": os.getenv("VC_TEMP"),
                "VC_ONNX_WEIGHTS": os.getenv("VC_ONNX_WEIGHTS"),
                "VC_BIAS_CAT": os.getenv("VC_BIAS_CAT"),
            },
            "selected_model_paths": list(_model_paths_selected),
            "available_providers": (list(ort.get_available_providers()) if ort else []),
            "selected_providers": list(_providers_selected),
            "onnxruntime_version": getattr(ort, "__version__", None) if ort else None,
            "ort_loaded": bool(ort is not None),
            "load_errors": list(_load_errors),
        })
    except Exception as e:
        info["error"] = str(e)
    base = get_runtime_info()
    base["debug"] = info
    return base
