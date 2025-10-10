from __future__ import annotations

import os
import numpy as np
import cv2
from typing import Dict, Any


def _to_uint8(img: np.ndarray) -> np.ndarray:
    img = np.clip(img, 0, 255)
    return img.astype(np.uint8)


def _gray_world_white_balance(img_rgb: np.ndarray) -> np.ndarray:
    img = img_rgb.astype(np.float32)
    means = np.maximum(1.0, img.reshape(-1, 3).mean(axis=0))
    gray_mean = float(means.mean())
    scale = gray_mean / means
    img_bal = img * scale
    return _to_uint8(img_bal)


def _adjust_gamma(img_rgb: np.ndarray, gamma: float) -> np.ndarray:
    if gamma is None or abs(gamma - 1.0) < 1e-3:
        return img_rgb
    inv_g = 1.0 / max(1e-6, gamma)
    table = (np.linspace(0, 1, 256) ** inv_g) * 255.0
    table = np.clip(table, 0, 255).astype(np.uint8)
    return cv2.LUT(img_rgb, table)


def _clahe_lab(img_rgb: np.ndarray, clip: float = 2.0, grid: int = 8) -> np.ndarray:
    lab = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=float(clip), tileGridSize=(grid, grid))
    l_enhanced = clahe.apply(l)
    lab_enhanced = cv2.merge((l_enhanced, a, b))
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2RGB)


def _bilateral(img_rgb: np.ndarray, d: int, sigma_color: float, sigma_space: float) -> np.ndarray:
    return cv2.bilateralFilter(img_rgb, d=int(d), sigmaColor=float(sigma_color), sigmaSpace=float(sigma_space))


def _denoise_colored(img_rgb: np.ndarray, h: float = 3.0, hColor: float = 3.0) -> np.ndarray:
    return cv2.fastNlMeansDenoisingColored(img_rgb, None, h=float(h), hColor=float(hColor), templateWindowSize=7, searchWindowSize=21)


def _glare_inpaint(img_rgb: np.ndarray, thresh: int = 250, max_ratio: float = 0.03, radius: int = 3) -> np.ndarray:
    hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    v = hsv[:, :, 2]
    mask = (v >= int(thresh)).astype(np.uint8) * 255
    # Keep only small highlight regions to avoid wiping clinically relevant areas
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    filtered = np.zeros_like(mask)
    total = mask.size
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area / float(total) <= max_ratio:
            filtered[labels == i] = 255
    if cv2.countNonZero(filtered) == 0:
        return img_rgb
    bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
    inpainted = cv2.inpaint(bgr, filtered, float(radius), cv2.INPAINT_TELEA)
    return cv2.cvtColor(inpainted, cv2.COLOR_BGR2RGB)


def _unsharp_mask(img_rgb: np.ndarray, amount: float = 0.35, sigma: float = 0.8) -> np.ndarray:
    blur = cv2.GaussianBlur(img_rgb, (0, 0), sigmaX=float(sigma))
    sharp = cv2.addWeighted(img_rgb, 1.0 + float(amount), blur, -float(amount), 0)
    return sharp


def _getf(env_key: str, default: float) -> float:
    try:
        return float(os.getenv(env_key, str(default)))
    except Exception:
        return default


def _geti(env_key: str, default: int) -> int:
    try:
        return int(float(os.getenv(env_key, str(default))))
    except Exception:
        return default


def _getb(env_key: str, default: bool) -> bool:
    val = str(os.getenv(env_key, str(int(default)))).strip().lower()
    return val in ("1", "true", "yes", "on")


def enhance_image_quality(image_array: np.ndarray) -> np.ndarray:
    """Enhance image quality using configurable OpenCV preprocessing.

    Steps (controlled by env vars):
      - Gray-world white balance: VC_PREP_GRAYWORLD=1
      - Gamma correction: VC_PREP_GAMMA=1.0 (no-op if 1.0)
      - CLAHE (LAB L channel): VC_PREP_CLAHE=1, VC_PREP_CLAHE_CLIP, VC_PREP_CLAHE_GRID
      - Bilateral filter (edge-preserving): VC_PREP_BILATERAL=0, *_D, *_SIGMA_COLOR, *_SIGMA_SPACE
      - Denoise colored (NLM): VC_PREP_DENOISE=0, *_H, *_HCOLOR
      - Glare inpainting: VC_PREP_DEGLARE=0, *_THRESH, *_MAX, *_RADIUS
      - Unsharp mask: VC_PREP_UNSHARP=1, *_AMOUNT, *_SIGMA
    """

    img = image_array.copy()

    # 1) White balance (Gray World)
    if _getb('VC_PREP_GRAYWORLD', True):
        img = _gray_world_white_balance(img)

    # 2) Gamma correction
    gamma = _getf('VC_PREP_GAMMA', 1.0)
    img = _adjust_gamma(img, gamma)

    # 3) CLAHE (LAB)
    if _getb('VC_PREP_CLAHE', True):
        clip = _getf('VC_PREP_CLAHE_CLIP', 2.0)
        grid = _geti('VC_PREP_CLAHE_GRID', 8)
        img = _clahe_lab(img, clip=clip, grid=grid)

    # 4) Optional edge-preserving smoothing / denoise (keep mild)
    if _getb('VC_PREP_BILATERAL', False):
        d = _geti('VC_PREP_BILATERAL_D', 7)
        sc = _getf('VC_PREP_BILATERAL_SIGMA_COLOR', 50.0)
        ss = _getf('VC_PREP_BILATERAL_SIGMA_SPACE', 50.0)
        img = _bilateral(img, d=d, sigma_color=sc, sigma_space=ss)
    elif _getb('VC_PREP_DENOISE', False):
        h = _getf('VC_PREP_DENOISE_H', 3.0)
        hc = _getf('VC_PREP_DENOISE_HCOLOR', 3.0)
        img = _denoise_colored(img, h=h, hColor=hc)

    # 5) Optional glare inpainting (very conservative)
    if _getb('VC_PREP_DEGLARE', False):
        thr = _geti('VC_PREP_DEGLARE_THRESH', 250)
        mx = _getf('VC_PREP_DEGLARE_MAX', 0.03)
        rad = _geti('VC_PREP_DEGLARE_RADIUS', 3)
        img = _glare_inpaint(img, thresh=thr, max_ratio=mx, radius=rad)

    # 6) Optional unsharp mask (mild)
    if _getb('VC_PREP_UNSHARP', True):
        amt = _getf('VC_PREP_UNSHARP_AMOUNT', 0.35)
        sig = _getf('VC_PREP_UNSHARP_SIGMA', 0.8)
        img = _unsharp_mask(img, amount=amt, sigma=sig)

    return img


def compute_image_quality(image_array: np.ndarray) -> Dict[str, Any]:
    """Compute simple image quality metrics and a quality score in [0,1]."""
    try:
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(image_array, cv2.COLOR_RGB2HSV)
        v = hsv[:, :, 2].astype(np.float32)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        lap_var = float(np.var(lap))
        lap_var_norm = float(lap_var / (lap_var + 300.0))
        mean_v = float(np.mean(v) / 255.0)
        dark_ratio = float(np.mean(v <= 25))
        bright_ratio = float(np.mean(v >= 230))
        score = 0.65 * lap_var_norm + 0.25 * (1.0 - abs(mean_v - 0.5) * 2.0) + 0.10 * (1.0 - (dark_ratio + bright_ratio))
        score = max(0.0, min(1.0, score))
        flag = 'ok' if score >= 0.45 and dark_ratio < 0.5 and bright_ratio < 0.35 else 'low'
        return {
            'lap_var_norm': lap_var_norm,
            'mean_brightness': mean_v,
            'dark_ratio': dark_ratio,
            'bright_ratio': bright_ratio,
            'quality_score': score,
            'quality_flag': flag,
        }
    except Exception:
        return {
            'lap_var_norm': 0.0,
            'mean_brightness': 0.0,
            'dark_ratio': 1.0,
            'bright_ratio': 0.0,
            'quality_score': 0.0,
            'quality_flag': 'low',
        }


def detect_eye_region(image_array: np.ndarray) -> np.ndarray:
    """Detect eye region in the image using cascade + fallbacks."""
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    eyes = eye_cascade.detectMultiScale(gray, 1.1, 4)
    if len(eyes) > 0:
        largest_eye = max(eyes, key=lambda e: e[2] * e[3])
        x, y, w, h = largest_eye
        return image_array[y:y + h, x:x + w]

    blur = cv2.medianBlur(gray, 5)
    H, W = gray.shape
    minR = max(10, int(min(H, W) * 0.06))
    maxR = max(minR + 10, int(min(H, W) * 0.30))
    circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=int(min(H, W) * 0.4),
                               param1=60, param2=30, minRadius=minR, maxRadius=maxR)
    if circles is not None and len(circles) > 0:
        circles = np.uint16(np.around(circles))
        cx, cy, r = circles[0][0]
        pad = int(r * 1.5)
        x1, x2 = max(0, cx - pad), min(W, cx + pad)
        y1, y2 = max(0, cy - pad), min(H, cy + pad)
        return image_array[y1:y2, x1:x2]

    H, W = image_array.shape[:2]
    min_dim = min(W, H)
    cx, cy = W // 2, H // 2
    offsets = [-int(0.12 * min_dim), 0, int(0.12 * min_dim)]
    centers = [(cx + dx, cy + dy) for dx in offsets for dy in offsets]
    crop_sizes = [int(min_dim * 0.70), int(min_dim * 0.55)]

    def score_crop(xc: int, yc: int, size: int):
        half = size // 2
        x1, x2 = max(0, xc - half), min(W, xc + half)
        y1, y2 = max(0, yc - half), min(H, yc + half)
        cw, ch = (x2 - x1), (y2 - y1)
        if cw < 64 or ch < 64:
            return (-1.0, (x1, y1, x2, y2))
        crop = image_array[y1:y2, x1:x2]
        gray_c = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        lap = cv2.Laplacian(gray_c, cv2.CV_64F)
        lap_var = float(np.var(lap))
        lap_norm = float(lap_var / (lap_var + 300.0))
        edges = cv2.Canny(cv2.GaussianBlur(gray_c, (5, 5), 0), 50, 150)
        hh, ww = gray_c.shape
        cx2, cy2 = ww // 2, hh // 2
        base_r = int(0.32 * min(hh, ww))
        mask_ring = np.zeros_like(gray_c, dtype=np.uint8)
        cv2.circle(mask_ring, (cx2, cy2), max(5, base_r), 255, thickness=max(2, base_r // 8))
        ring_density = float(np.count_nonzero(edges[mask_ring > 0])) / float(np.count_nonzero(mask_ring) or 1)
        hsv_c = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
        v = hsv_c[:, :, 2]
        highlight_ratio = float(np.mean(v >= 245))
        bonus = 0.0
        try:
            blur = cv2.medianBlur(gray_c, 5)
            minR = max(8, int(min(hh, ww) * 0.10))
            maxR = max(minR + 6, int(min(hh, ww) * 0.45))
            circles = cv2.HoughCircles(blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=int(min(hh, ww) * 0.5),
                                       param1=60, param2=30, minRadius=minR, maxRadius=maxR)
            if circles is not None and len(circles) > 0:
                bonus = 0.08
        except Exception:
            pass
        score = 0.45 * lap_norm + 0.40 * ring_density + 0.15 * (1.0 - min(1.0, highlight_ratio)) + bonus
        return (score, (x1, y1, x2, y2))

    best_score = -1.0
    best_rect = None
    for size in crop_sizes:
        for (cx_i, cy_i) in centers:
            sc, rect = score_crop(cx_i, cy_i, size)
            if sc > best_score:
                best_score, best_rect = sc, rect

    if best_rect is not None and best_score > 0:
        x1, y1, x2, y2 = best_rect
        roi = image_array[y1:y2, x1:x2]
        if roi.shape[0] >= 80 and roi.shape[1] >= 80:
            return roi

    center_x, center_y = W // 2, H // 2
    crop_size = int(min_dim * 0.80)
    start_x = max(0, center_x - crop_size // 2)
    end_x = min(W, center_x + crop_size // 2)
    start_y = max(0, center_y - crop_size // 2)
    end_y = min(H, center_y + crop_size // 2)
    return image_array[start_y:end_y, start_x:end_x]


def analyze_eye_features(eye_region: np.ndarray) -> Dict[str, Any]:
    """Compute OpenCV-based metrics and derived indicators."""
    red_channel = eye_region[:, :, 0].astype(np.float32)
    green_channel = eye_region[:, :, 1].astype(np.float32)
    blue_channel = eye_region[:, :, 2].astype(np.float32)
    redness_score = float(np.mean(red_channel / (green_channel + blue_channel + 1.0)))

    gray = cv2.cvtColor(eye_region, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(eye_region, cv2.COLOR_RGB2HSV)
    h_ch, s_ch, v_ch = cv2.split(hsv)

    # Proportion of saturated highlights; useful to detect glare and avoid false opacities
    highlight_ratio = float(np.mean(gray >= 245))

    h, w = gray.shape
    gray_blur = cv2.medianBlur(gray, 5)
    min_r = max(8, int(min(h, w) * 0.12))
    max_r = max(min_r + 4, int(min(h, w) * 0.45))
    circles = cv2.HoughCircles(gray_blur, cv2.HOUGH_GRADIENT, dp=1.2, minDist=int(min(h, w) * 0.4),
                               param1=60, param2=30, minRadius=min_r, maxRadius=max_r)
    if circles is not None and len(circles) > 0:
        circles = np.uint16(np.around(circles))
        x_c, y_c, r_c = circles[0][0]
    else:
        x_c, y_c = w // 2, h // 2
        r_c = int(min(h, w) * 0.35)

    # Build iris mask (inner disc) and sclera ring mask (ring outside iris)
    mask_iris = np.zeros_like(gray, dtype=np.uint8)
    r_inner = int(r_c * 0.85)
    cv2.circle(mask_iris, (int(x_c), int(y_c)), max(5, r_inner), 255, -1)
    mask_bool = mask_iris.astype(bool)

    mask_sclera = np.zeros_like(gray, dtype=np.uint8)
    min_dim = min(h, w)
    r_outer2 = int(min(r_c * 1.60, 0.48 * min_dim))
    r_outer1 = max(r_inner + 2, int(min(r_c * 1.10, r_outer2 - 2)))
    if r_outer2 > r_outer1 + 1:
        cv2.circle(mask_sclera, (int(x_c), int(y_c)), r_outer2, 255, -1)
        cv2.circle(mask_sclera, (int(x_c), int(y_c)), r_outer1, 0, -1)
    mask_sclera_bool = mask_sclera.astype(bool)

    # Conjunctival band (lower region near eyelid) to capture palpebral redness
    mask_conj = np.zeros_like(gray, dtype=np.uint8)
    y1_conj = int(min(h - 1, y_c + 0.25 * r_inner))
    y2_conj = int(min(h, y_c + 1.10 * r_inner))
    x1_conj = int(max(0, x_c - 1.15 * r_inner))
    x2_conj = int(min(w, x_c + 1.15 * r_inner))
    if (y2_conj - y1_conj) > 4 and (x2_conj - x1_conj) > 4:
        mask_conj[y1_conj:y2_conj, x1_conj:x2_conj] = 255
    mask_conj_bool = mask_conj.astype(bool)

    highlight_mask = (gray >= 245) | (v_ch >= 245)
    mask_clean = mask_bool & (~highlight_mask)
    mask_clean_sclera = mask_sclera_bool & (~highlight_mask)
    # Restrict sclera to low saturation, relatively bright pixels (avoid eyelid/skin)
    try:
        sat_max_scl = int(float(os.getenv('VC_SCLERA_S_MAX', '90')))
        v_min_scl = int(float(os.getenv('VC_SCLERA_V_MIN', '140')))
    except Exception:
        sat_max_scl, v_min_scl = 90, 140
    mask_sclera_gate = (s_ch <= sat_max_scl) & (v_ch >= v_min_scl)
    mask_clean_sclera = mask_clean_sclera & mask_sclera_gate

    # Conjunctival gate: allow higher saturation and moderate brightness to include red tissue
    try:
        sat_max_conj = int(float(os.getenv('VC_CONJ_S_MAX', '150')))
        v_min_conj = int(float(os.getenv('VC_CONJ_V_MIN', '90')))
    except Exception:
        sat_max_conj, v_min_conj = 150, 90
    mask_clean_conj = mask_conj_bool & (~highlight_mask) & (s_ch <= sat_max_conj) & (v_ch >= v_min_conj)
    if np.count_nonzero(mask_clean) < 50:
        mask_clean = mask_bool
    if np.count_nonzero(mask_clean_sclera) < 50:
        mask_clean_sclera = mask_sclera_bool

    gray_vals = gray[mask_clean].astype(np.float32)
    v_vals = v_ch[mask_clean].astype(np.float32)
    s_vals = s_ch[mask_clean].astype(np.float32)

    std_gray = (np.std(gray_vals) / 255.0) if gray_vals.size else 0.0
    mean_v = (np.mean(v_vals) / 255.0) if v_vals.size else 0.0
    mean_s = (np.mean(s_vals) / 255.0) if s_vals.size else 0.0

    bright_thresh = 200
    sat_low_thresh = 80
    bright_mask = (v_ch >= bright_thresh)
    low_sat_mask = (s_ch <= sat_low_thresh)
    whiteness_mask = mask_clean & bright_mask & low_sat_mask
    central_whiteness = float(np.count_nonzero(whiteness_mask)) / float(np.count_nonzero(mask_bool) or 1)

    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges_in_mask = float(np.count_nonzero(edges[mask_bool] > 0)) / float(np.count_nonzero(mask_bool) or 1)
    edges_in_sclera = float(np.count_nonzero(edges[mask_clean_sclera] > 0)) / float(np.count_nonzero(mask_clean_sclera) or 1)
    edges_in_conj = float(np.count_nonzero(edges[mask_clean_conj] > 0)) / float(np.count_nonzero(mask_clean_conj) or 1)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    lap_vals = lap[mask_clean]
    lap_var = float(np.var(lap_vals)) if lap_vals.size else 0.0
    lap_norm = min(1.0, lap_var / 200.0)
    blur_score = 1.0 - lap_norm

    # Rebalance opacity components to reduce over-reliance on low edges/blur
    opacity_components = [
        0.28 * (1.0 - std_gray),
        0.28 * mean_v,
        0.22 * (1.0 - mean_s),
        0.12 * (1.0 - edges_in_mask),
        0.10 * blur_score,
    ]
    opacity_raw = float(np.sum(opacity_components))

    # Penalize opacity under strong glare conditions
    # When highlight_ratio > ~1%, start penalizing up to ~0.15 at ~11% highlights
    glare_penalty_factor = min(1.0, max(0.0, (highlight_ratio - 0.01) / 0.10))
    glare_penalty = 0.15 * glare_penalty_factor
    opacity_score = float(max(0.0, min(1.0, opacity_raw - glare_penalty)))
    vascular_density = float(edges_in_mask)
    sclera_red_vals = (red_channel[mask_clean_sclera] / (green_channel[mask_clean_sclera] + blue_channel[mask_clean_sclera] + 1.0)) if np.count_nonzero(mask_clean_sclera) > 0 else np.array([0.0], dtype=np.float32)
    sclera_redness = float(np.mean(sclera_red_vals)) if sclera_red_vals.size else 0.0
    sclera_vascular_density = float(edges_in_sclera)
    conj_red_vals = (red_channel[mask_clean_conj] / (green_channel[mask_clean_conj] + blue_channel[mask_clean_conj] + 1.0)) if np.count_nonzero(mask_clean_conj) > 0 else np.array([0.0], dtype=np.float32)
    conj_redness = float(np.mean(conj_red_vals)) if conj_red_vals.size else 0.0
    conj_vascular_density = float(edges_in_conj)

    return {
        'redness_score': float(redness_score),
        'opacity_score': opacity_score,
        'vascular_density': vascular_density,
        'highlight_ratio': float(highlight_ratio),
        'central_whiteness': float(central_whiteness),
        'brightness_mean': float(mean_v),
        'texture_index': float(lap_norm),
        'sclera_redness': float(sclera_redness),
        'sclera_vascular_density': float(sclera_vascular_density),
        'conj_redness': float(conj_redness),
        'conj_vascular_density': float(conj_vascular_density),
    }
