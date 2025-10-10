from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import os
import time
import numpy as np
from PIL import Image

from ..ports.repositories import AnalysisRepo, AnalysisCreate
from ..ports.storage import FileStorage
from ..ports.ai_services import EyeDiseaseDetector
from ...domain.image_processing import (
    enhance_image_quality,
    detect_eye_region,
    compute_image_quality,
    analyze_eye_features,
)
from ...domain.diagnosis import rule_based_diagnosis


@dataclass
class UploadAndAnalyzeInput:
    user_id: int
    image_file: Any  # file-like object readable by PIL
    enable_tta: bool = True
    enable_quality: bool = True
    p_high: float = 0.75
    p_mid: float = 0.55


class UploadAndAnalyzeImage:
    def __init__(
        self,
        repo: AnalysisRepo,
        storage: FileStorage,
        detector: EyeDiseaseDetector,
    ) -> None:
        self.repo = repo
        self.storage = storage
        self.detector = detector

    def execute(self, inp: UploadAndAnalyzeInput) -> Dict[str, Any]:
        start_time = time.time()

        # Load image with PIL and get RGB numpy array
        pil_image = Image.open(inp.image_file)
        if pil_image.mode != 'RGB':
            pil_image = pil_image.convert('RGB')
        image_array = np.array(pil_image)

        # Enhance and crop
        enhanced = enhance_image_quality(image_array)
        eye_region = detect_eye_region(enhanced)

        # Optional preview storage
        preview_url = self.storage.save_processed_preview(eye_region)

        # Metrics and quality
        opencv_results = analyze_eye_features(eye_region)
        quality = compute_image_quality(eye_region) if inp.enable_quality else None

        # Inference via detector
        onnx_probs: Optional[Dict[str, float]] = None
        tta: Optional[Dict[str, Any]] = None
        if inp.enable_tta:
            try:
                tta = self.detector.infer_tta(eye_region)
            except Exception:
                tta = None
        if tta is None:
            try:
                onnx_probs = self.detector.infer_probs(eye_region)
            except Exception:
                onnx_probs = None
        else:
            probs = tta.get('probs') if isinstance(tta, dict) else None
            if isinstance(probs, dict):
                onnx_probs = {str(k): float(v) for k, v in probs.items()}

        # Runtime info can be included if detector provides it via tta
        runtime = None
        if tta and isinstance(tta.get('model_count'), (int, float)):
            runtime = {
                'loaded': True,
                'model_count': int(tta.get('model_count') or 0),
                'providers': list(tta.get('providers') or []),
                'class_names': list(tta.get('class_names') or []),
                'img_size': int(tta.get('img_size')) if tta.get('img_size') else None,
            }

        # Rule-based decision from domain and fusion
        ai_results = rule_based_diagnosis(opencv_results)
        fused_diag = ai_results['diagnosis']
        fused_sev = ai_results['severity']
        fused_conf = ai_results['confidence']
        explanation_extra = []

        if onnx_probs is not None and 'cataracts' in onnx_probs:
            p_cat = onnx_probs['cataracts']
            explanation_extra.append(f"[ONNX] P(cataratas)={p_cat:.2f}.")
            if p_cat >= inp.p_high:
                fused_diag = 'cataracts'
                fused_sev = 'moderate' if p_cat < 0.85 else 'severe'
                fused_conf = max(fused_conf, p_cat)
            elif inp.p_mid <= p_cat < inp.p_high:
                if ai_results['diagnosis'] != 'cataracts' and opencv_results.get('opacity_score', 0.0) >= 0.62:
                    fused_diag = 'cataracts'
                    fused_sev = 'moderate'
                    fused_conf = max(fused_conf, 0.7 * p_cat + 0.3 * ai_results['confidence'])

        # Aggregate confidence (configurable weights)
        def _getf(env: str, default: float) -> float:
            try:
                return float(os.getenv(env, str(default)))
            except Exception:
                return default

        has_onnx = bool(onnx_probs and 'cataracts' in onnx_probs)
        if has_onnx:
            w_r = _getf('VC_CONF_W_REDNESS_ONNX', 0.22)
            w_o = _getf('VC_CONF_W_OPACITY_ONNX', 0.28)
            w_rules = _getf('VC_CONF_W_RULES_ONNX', 0.40)
            w_onnx = _getf('VC_CONF_W_ONNX', 0.10)
            base_conf = (
                w_r * float(opencv_results['redness_score']) +
                w_o * float(opencv_results['opacity_score']) +
                w_rules * float(ai_results['confidence']) +
                w_onnx * float(onnx_probs['cataracts'])
            )
        else:
            w_r = _getf('VC_CONF_W_REDNESS', 0.28)
            w_o = _getf('VC_CONF_W_OPACITY', 0.32)
            w_rules = _getf('VC_CONF_W_RULES', 0.40)
            base_conf = (
                w_r * float(opencv_results['redness_score']) +
                w_o * float(opencv_results['opacity_score']) +
                w_rules * float(ai_results['confidence'])
            )

        # Agreement boosts: small positive nudges when signals align
        diag = ai_results.get('diagnosis')
        try:
            o = float(opencv_results.get('opacity_score', 0.0))
            cw = float(opencv_results.get('central_whiteness', 0.0))
            r = float(opencv_results.get('redness_score', 0.0))
            v = float(opencv_results.get('vascular_density', 0.0))
            v_scl = float(opencv_results.get('sclera_vascular_density', v))
            h_ratio = float(opencv_results.get('highlight_ratio', 0.0))
        except Exception:
            o = cw = r = v = v_scl = h_ratio = 0.0

        opacity_cataract_th = _getf('VC_OPACITY_CAT_TH', 0.66)
        redness_conj_th = _getf('VC_REDNESS_CONJ_TH', 0.66)
        vascular_elev_th = _getf('VC_VASC_ELEVATED_TH', 0.12)
        glare_high_th = _getf('VC_GLARE_HIGH_TH', 0.03)

        boost = 0.0
        if diag == 'cataracts':
            if (o >= opacity_cataract_th) or (cw >= 0.35):
                boost += 0.05
            if has_onnx and float(onnx_probs['cataracts']) >= 0.60:
                boost += 0.05
            if h_ratio < glare_high_th:
                boost += 0.02
        elif diag == 'conjunctivitis':
            if (r >= redness_conj_th) and ((v + v_scl) * 0.5 >= vascular_elev_th):
                boost += 0.05
            if h_ratio < glare_high_th:
                boost += 0.01
        elif diag == 'opacidades_menores':
            if (o >= _getf('VC_OPACITY_MINOR_TH', 0.46)) and (h_ratio < glare_high_th * 1.2):
                boost += 0.03

        base_conf = max(0.0, min(1.0, base_conf + boost))

        if inp.enable_tta and tta and isinstance(tta.get('uncertainty'), dict):
            import numpy as _np
            ent = float(tta['uncertainty'].get('entropy') or 0.0)
            max_ent = _np.log(max(1, len(tta.get('class_names') or [])) or 3)
            max_ent = max(max_ent, 1.0)
            certainty = 1.0 - float(ent) / float(max_ent)
            certainty = max(0.0, min(1.0, certainty))
            tta_w = _getf('VC_CONF_TTA_CERTAINTY_W', 0.25)
            base_conf = (1.0 - tta_w) * base_conf + tta_w * certainty

        if inp.enable_quality and quality and quality.get('quality_flag') == 'low':
            max_cap = _getf('VC_QUALITY_LOW_MAX', 0.50)
            base_conf = min(base_conf, max_cap)

        # Diagnosis-specific minimums (to avoid ultrabajas cuando hay patrón claro)
        min_map = {
            'cataracts': _getf('VC_CONF_MIN_CATARACTS', 0.55),
            'conjunctivitis': _getf('VC_CONF_MIN_CONJUNCTIVITIS', 0.45),
            'opacidades_menores': _getf('VC_CONF_MIN_MINOR_OPACITY', 0.38),
            'redness_minor': _getf('VC_CONF_MIN_REDNESS_MINOR', 0.35),
            'normal': _getf('VC_CONF_MIN_NORMAL', 0.25),
        }
        base_conf = max(base_conf, float(min_map.get(fused_diag, 0.0)))

        # Optional gamma calibration to slightly lift medias
        gamma = _getf('VC_CONF_GAMMA', 0.90)
        gamma = max(0.05, min(2.0, gamma))
        try:
            calibrated = base_conf ** gamma
        except Exception:
            calibrated = base_conf

        final_confidence = float(max(0.0, min(1.0, calibrated)))

        duration = time.time() - start_time

        # Co-findings summary
        co = ai_results.get('co_findings') or []
        co_sentence = ''
        if isinstance(co, list) and co:
            parts = []
            for item in co[:3]:
                try:
                    parts.append(f"{item.get('label')} ({item.get('level')})")
                except Exception:
                    continue
            if parts:
                co_sentence = " Co-hallazgos: " + ", ".join(parts) + "."

        record = self.repo.create(AnalysisCreate(
            user_id=inp.user_id,
            image_file=inp.image_file,
            diagnosis=fused_diag,
            severity=fused_sev,
            confidence_score=final_confidence,
            opencv_redness_score=float(opencv_results['redness_score']),
            opencv_opacity_score=float(opencv_results['opacity_score']),
            opencv_vascular_density=float(opencv_results['vascular_density']),
            ai_analysis_text=(ai_results['explanation'] + (" " + " ".join(explanation_extra) if explanation_extra else "") + co_sentence),
            ai_confidence=max(ai_results['confidence'], onnx_probs['cataracts']) if (onnx_probs and 'cataracts' in onnx_probs) else ai_results['confidence'],
            ai_raw_response={
                'rules': ai_results,
                'opencv': opencv_results,
                'onnx': onnx_probs or {},
                'uncertainty': (tta.get('uncertainty') if (inp.enable_tta and tta) else {}),
                'per_aug': (tta.get('per_aug') if tta else []),
                'runtime': (runtime or {}),
                'quality': (quality or {}),
                'co_findings': co,
                'processed_image_url': preview_url,
            },
            recommendations=ai_results['recommendations'],
            medical_advice=_generate_conservative_advice(ai_results),
            analysis_duration=duration,
        ))

        return {
            'record': record,
            'processed_image_url': preview_url,
            'quality': quality,
            'uncertainty': (tta.get('uncertainty') if (inp.enable_tta and tta) else None),
            'runtime': runtime,
            'co_findings': co,
        }


def _generate_conservative_advice(ai_results: Dict[str, Any]) -> str:
    base_advice = "Este es un análisis asistido por IA y no reemplaza un diagnóstico médico profesional. "
    if ai_results['diagnosis'] in ['conjunctivitis', 'cataracts']:
        return base_advice + "Por favor acuda a un/a oftalmólogo/a o profesional de la salud para una evaluación y tratamiento adecuados."
    elif ai_results['diagnosis'] in ['opacidades_menores', 'redness_minor']:
        return base_advice + "Monitoree su condición y consulte a un profesional si los síntomas persisten o empeoran."
    else:
        return base_advice + "Si presenta molestias o dudas sobre su salud ocular, consulte con un profesional médico."


# Removed local _rule_based_diagnosis to avoid duplication; using domain.rule_based_diagnosis
