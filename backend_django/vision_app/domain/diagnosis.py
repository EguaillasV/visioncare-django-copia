"""Domain diagnosis rules.

Pure rule-based logic that interprets OpenCV metrics into a diagnosis.
This module must not depend on frameworks or adapters.
"""

from __future__ import annotations

from typing import Dict, Any
import os


def _getf(env_name: str, default: float) -> float:
	try:
		return float(os.getenv(env_name, str(default)))
	except Exception:
		return default


def rule_based_diagnosis(opencv_results: Dict[str, Any]) -> Dict[str, Any]:
	r = float(opencv_results.get('redness_score', 0.0))
	o = float(opencv_results.get('opacity_score', 0.0))
	v = float(opencv_results.get('vascular_density', 0.0))
	h = float(opencv_results.get('highlight_ratio', 0.0))
	cw = float(opencv_results.get('central_whiteness', 0.0))
	r_scl = float(opencv_results.get('sclera_redness', r))
	v_scl = float(opencv_results.get('sclera_vascular_density', v))
	r_conj = float(opencv_results.get('conj_redness', r_scl))
	v_conj = float(opencv_results.get('conj_vascular_density', v_scl))

	diagnosis = 'normal'
	severity = 'normal'
	explanation_parts = []
	co_findings = []

	redness_minor_th = _getf('VC_REDNESS_MINOR_TH', 0.50)
	redness_conjunctivitis_th = _getf('VC_REDNESS_CONJ_TH', 0.62)
	opacity_minor_th = _getf('VC_OPACITY_MINOR_TH', 0.46)
	opacity_cataract_th = _getf('VC_OPACITY_CAT_TH', 0.66)
	vascular_elevated_th = _getf('VC_VASC_ELEVATED_TH', 0.14)
	vascular_low_th = _getf('VC_VASC_LOW_TH', 0.22)
	glare_high_th = _getf('VC_GLARE_HIGH_TH', 0.03)
	cw_minor_th = _getf('VC_CW_MINOR_TH', 0.24)
	sclera_red_minor_th = _getf('VC_SCLERA_RED_MINOR_TH', 0.42)
	sclera_red_strong_th = _getf('VC_SCLERA_RED_STRONG_TH', 0.60)
	conj_red_minor_th = _getf('VC_CONJ_RED_MINOR_TH', 0.52)
	conj_red_strong_th = _getf('VC_CONJ_RED_STRONG_TH', 0.58)
	conj_vasc_min = _getf('VC_CONJ_VASC_MIN', 0.10)

	vb = float(opencv_results.get('brightness_mean', 0.0))
	tex = float(opencv_results.get('texture_index', 0.0))
	strong_opacity_case = False

	# Cataracts
	if (o >= 0.88 and vb >= 0.70 and tex <= 0.015 and r <= 0.58 and cw >= 0.42):
		diagnosis = 'cataracts'
		strong_opacity_case = True
		severity = 'severe' if (o >= 0.92 or cw >= 0.50) else 'moderate'
		explanation_parts.append(
			f"Patrón de iris muy blanqueado: opacidad {o:.2f}, brillo {vb:.2f}, textura baja {tex:.3f}, blancura central {cw:.2f}."
		)
	elif (o >= 0.82 and vb >= 0.62 and tex <= 0.020 and r < 0.64 and cw >= 0.35 and h < 0.06):
		diagnosis = 'cataracts'
		severity = 'severe' if (o >= 0.88 or cw >= 0.42) else 'moderate'
		explanation_parts.append(
			f"Opacidad alta ({o:.2f}), brillo {vb:.2f}, textura baja {tex:.3f}, blancura central {cw:.2f}."
		)
	elif (o >= 0.70 and vb >= 0.55 and h < 0.025 and r < 0.62 and cw >= 0.30 and tex <= 0.08):
		diagnosis = 'cataracts'
		severity = 'severe' if (o >= 0.78 or cw >= 0.35) else 'moderate'
		explanation_parts.append(
			f"Opacidad elevada ({o:.2f}), brillo {vb:.2f}, blancura central {cw:.2f} con poca textura {tex:.3f}."
		)
	elif ((o >= 0.72 or cw >= 0.38) and vb >= 0.58 and r < 0.64 and tex <= 0.022):
		diagnosis = 'cataracts'
		severity = 'moderate'
		explanation_parts.append(
			f"Indicadores compatibles con cataratas: opacidad {o:.2f}/blancura {cw:.2f}, brillo {vb:.2f}, textura baja {tex:.3f}."
		)

	# Redness/Conjunctivitis
	r_mix = (0.25 * r + 0.50 * r_scl + 0.25 * r_conj)
	v_mix = (0.25 * v + 0.50 * v_scl + 0.25 * v_conj)
	if diagnosis == 'normal' and (r_mix >= redness_conjunctivitis_th and (v_mix >= vascular_elevated_th or max(r_scl, r_conj) >= sclera_red_strong_th)):
		diagnosis = 'conjunctivitis'
		severity = 'moderate' if r < (redness_conjunctivitis_th + 0.10) else 'severe'
		explanation_parts.append(
			f"Rojez alta en esclera/ojos ({r_scl:.2f}/{r:.2f}) con vascularidad ({v_scl:.2f}/{v:.2f}) compatible con conjuntivitis."
		)
	elif diagnosis == 'normal' and (r_conj >= conj_red_strong_th and v_conj >= max(vascular_elevated_th - 0.02, 0.08)):
		diagnosis = 'conjunctivitis'
		severity = 'moderate'
		explanation_parts.append(
			f"Rojez conjuntival alta ({r_conj:.2f}) con vascularidad {v_conj:.2f}."
		)
	elif diagnosis == 'normal' and (r_mix >= redness_minor_th and (v_mix >= vascular_elevated_th * 0.92 or max(r_scl, r_conj) >= sclera_red_minor_th)):
		diagnosis = 'redness_minor'
		severity = 'mild'
		explanation_parts.append(f"Rojez leve (sclera/ojos {r_scl:.2f}/{r:.2f}) con vascularidad {v_scl:.2f}/{v:.2f}.")
	elif diagnosis == 'normal' and (r_conj >= conj_red_minor_th and v_conj >= conj_vasc_min):
		diagnosis = 'redness_minor'
		severity = 'mild'
		explanation_parts.append(f"Rojez conjuntival leve ({r_conj:.2f}) con vascularidad {v_conj:.2f}.")

	# Minor opacities
	if diagnosis == 'normal' and o >= opacity_minor_th and h < (glare_high_th * 1.2) and (r_mix < redness_minor_th or v_mix < vascular_elevated_th * 0.9) and (cw >= cw_minor_th):
		diagnosis = 'opacidades_menores'
		severity = 'mild'
		if h >= glare_high_th:
			explanation_parts.append(f"Opacidad leve ({o:.2f}) con reflejos ({h*100:.1f}% zona brillante).")
		else:
			explanation_parts.append(f"Opacidad leve ({o:.2f}).")

	# Confidence from rules
	if (0.25*v + 0.50*v_scl + 0.25*v_conj) >= (vascular_elevated_th * 0.9) or (v_conj >= conj_vasc_min and max(r, r_scl, r_conj) >= redness_minor_th):
		conf_r = min(max((max(r, r_scl) - redness_minor_th) / (redness_conjunctivitis_th - redness_minor_th + 1e-6), 0), 1)
	else:
		conf_r = 0.0
	conf_o = min(max((o - opacity_minor_th) / (max(0.01, 0.80) - opacity_minor_th + 1e-6), 0), 1)
	conf_w = min(max((cw - 0.22) / (max(0.23, 0.38) - 0.22 + 1e-6), 0), 1)
	base_conf = 0.58 * conf_w + 0.35 * conf_o + 0.07 * conf_r
	if r >= redness_conjunctivitis_th and o >= opacity_cataract_th:
		base_conf = min(1.0, base_conf + 0.2)
	if h >= glare_high_th:
		penalty = 0.03 if (diagnosis == 'cataracts') else 0.18
		base_conf = max(0.0, base_conf - penalty)

	if diagnosis == 'conjunctivitis':
		if (o >= opacity_minor_th and v <= 0.28) or (cw >= 0.35) or (o >= 0.55 and h < glare_high_th):
			level = 'likely' if (o >= opacity_cataract_th and v <= 0.22) else 'possible'
			co_findings.append({'label': 'cataracts', 'level': level, 'score': float(o)})
			explanation_parts.append(
				("Además, se observan indicios compatibles con cataratas "
				 f"(opacidad {o:.2f}{', blancura central alta' if cw >= 0.35 else ''}).")
			)
	if diagnosis == 'cataracts':
		if r >= redness_minor_th and v >= vascular_elevated_th:
			level = 'likely' if r >= redness_conjunctivitis_th else 'possible'
			co_findings.append({'label': 'conjunctivitis', 'level': level, 'score': float(r)})
			explanation_parts.append("Además, se aprecia rojez con incremento vascular compatibles con conjuntivitis.")

	explanation_parts.append(
		f"[Métricas] opacidad={o:.2f}, vascular={v:.2f} (esclera {v_scl:.2f}, conjuntiva {v_conj:.2f}), rojez={r:.2f} (esclera {r_scl:.2f}, conjuntiva {r_conj:.2f}), blancura={cw:.2f}, reflejos={h:.2f}."
	)

	recommendations = []
	if diagnosis == 'conjunctivitis':
		recommendations.append("Higiene ocular, evitar frotar los ojos, lágrimas artificiales.")
	if diagnosis == 'cataracts':
		recommendations.append("Evaluación oftalmológica para valorar tratamiento.")
	if diagnosis in ('opacidades_menores', 'redness_minor'):
		recommendations.append("Monitoreo de síntomas; consulta si persisten o empeoran.")
	if diagnosis == 'normal':
		recommendations.append("Mantener hábitos saludables y controles periódicos si hay molestias.")

	return {
		'diagnosis': diagnosis,
		'severity': severity,
		'confidence': float(max(0.0, min(1.0, base_conf))),
		'explanation': " ".join(explanation_parts) if explanation_parts else "Sin hallazgos relevantes según métricas calculadas.",
		'recommendations': " ".join(recommendations),
		'co_findings': co_findings,
	}


__all__ = ["rule_based_diagnosis"]
