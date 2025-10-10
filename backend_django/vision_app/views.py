import os
from datetime import datetime
from io import BytesIO
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from .models import User, Analysis
from django.db import IntegrityError
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
    AnalysisSerializer, AnalysisCreateSerializer, AnalysisHistorySerializer,
    PasswordChangeSerializer,
)
from .infer import get_runtime_debug

# Hexagonal adapters and use case
from .application.use_cases.upload_and_analyze_image import UploadAndAnalyzeInput
from .config.container import get_analysis_use_case

# OpenAI removed

class RegisterView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = serializer.save()
        except IntegrityError as e:
            # Map common unique constraints to friendly messages
            msg = str(e)
            detail = {'non_field_errors': 'No se pudo registrar'}
            lowered = msg.lower()
            if 'email' in lowered:
                detail = {'email': 'Este correo ya está registrado'}
            elif 'username' in lowered:
                detail = {'username': 'Este usuario ya está registrado'}
            elif 'cedula' in lowered:
                detail = {'cedula': 'Esta cédula ya está registrada'}
            return Response(detail, status=status.HTTP_400_BAD_REQUEST)

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Usuario registrado correctamente',
            'user': UserProfileSerializer(user, context={"request": request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    """User login endpoint"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Inicio de sesión exitoso',
            'user': UserProfileSerializer(user, context={"request": request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

class ProfileView(APIView):
    """Retrieve and update the authenticated user's profile."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return Response(serializer.data)

    def put(self, request):
        serializer = UserProfileSerializer(instance=request.user, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(instance=request.user, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class ChangePasswordView(APIView):
    """Allow authenticated user to change password."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        new_password = serializer.validated_data['new_password']
        user = request.user
        user.set_password(new_password)
        user.save()
        return Response({"message": "Contraseña actualizada correctamente"}, status=status.HTTP_200_OK)

class UploadAvatarView(APIView):
    """Upload or replace the authenticated user's avatar image."""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        file = request.FILES.get('avatar') or request.FILES.get('file') or request.FILES.get('image')
        if not file:
            return Response({"error": "No se proporcionó archivo 'avatar'"}, status=status.HTTP_400_BAD_REQUEST)
        # Basic validations
        if file.size > 5 * 1024 * 1024:  # 5MB
            return Response({"error": "La imagen no puede exceder 5MB"}, status=status.HTTP_400_BAD_REQUEST)
        # Allow common image types for avatars
        allowed = {'image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'}
        if getattr(file, 'content_type', None) not in allowed:
            return Response({"error": "Solo se permiten imágenes JPEG/PNG/WEBP/GIF"}, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.avatar = file
        user.save()
        data = UserProfileSerializer(user, context={"request": request}).data
        # Also include avatar_url at the top-level for convenient frontend consumption
        return Response({"message": "Avatar actualizado", "avatar_url": data.get("avatar_url"), "user": data}, status=status.HTTP_200_OK)

def rule_based_diagnosis(opencv_results):
    """Derive diagnosis, severity, confidence, explanation and recommendations based on OpenCV metrics."""
    r = opencv_results.get('redness_score', 0.0)
    o = opencv_results.get('opacity_score', 0.0)
    v = opencv_results.get('vascular_density', 0.0)
    h = opencv_results.get('highlight_ratio', 0.0)
    cw = opencv_results.get('central_whiteness', 0.0)

    diagnosis = 'normal'
    severity = 'normal'
    explanation_parts = []
    co_findings = []  # secondary concurrent hints

    # Simple thresholds (tunable)
    # Thresholds can be tuned via environment variables to control sensitivity
    try:
        # Requested: rojez moderada a partir de 0.50
        redness_minor_th = float(os.getenv('VC_REDNESS_MINOR_TH', '0.50'))
    except Exception:
        redness_minor_th = 0.50
    try:
        redness_conjunctivitis_th = float(os.getenv('VC_REDNESS_CONJ_TH', '0.66'))  # was 0.62
    except Exception:
        redness_conjunctivitis_th = 0.66
    # Requested: opacidades menores a partir de 0.40
    opacity_minor_th = 0.40
    opacity_cataract_th = 0.62
    try:
        vascular_elevated_th = float(os.getenv('VC_VASC_ELEVATED_TH', '0.10'))  # was 0.08
    except Exception:
        vascular_elevated_th = 0.10
    vascular_low_th = 0.22
    glare_high_th = 0.025
    strong_opacity_th = 0.80
    whiteness_cataract_th = 0.35

    # Redness-driven conditions
    if r >= redness_conjunctivitis_th and v >= vascular_elevated_th:
        diagnosis = 'conjunctivitis'
        # Requested: corte de severidad a 0.60 (nota: dado r>=0.66, usualmente será 'severe')
        severity = 'moderate' if r < 0.60 else 'severe'
        explanation_parts.append(f"Elevada rojez ({r:.2f}) y densidad vascular ({v:.2f}) sugieren conjuntivitis.")
    elif r >= redness_minor_th:
        diagnosis = 'redness_minor'
        severity = 'mild'
        explanation_parts.append(f"Rojez moderada ({r:.2f}) sin incremento marcado de vascularización.")

    # Opacity-driven conditions (may override if stronger)
    # Implement requested cataract rules using brightness_mean (vb) and texture_index (tex)
    vb = float(opencv_results.get('brightness_mean', 0.0))  # HSV-V mean [0,1]
    tex = float(opencv_results.get('texture_index', 0.0))    # lap_norm [0,1], high=more texture
    strong_opacity_case = False

    # 1) Ultra-strong rule (prioritize even with glare)
    if (o >= 0.88 and vb >= 0.70 and tex <= 0.015 and r <= 0.55 and cw >= 0.42):
        diagnosis = 'cataracts'
        strong_opacity_case = True
        severity = 'severe' if (o >= 0.92 or cw >= 0.50) else 'moderate'
        explanation_parts.append(
            f"Patrón de iris muy blanqueado: opacidad {o:.2f}, brillo {vb:.2f}, textura baja {tex:.3f}, blancura central {cw:.2f}."
        )
    # 2) Strong rule (robust to moderate glare)
    elif (o >= 0.82 and vb >= 0.62 and tex <= 0.020 and r < 0.62 and cw >= 0.35 and h < 0.06):
        diagnosis = 'cataracts'
        severity = 'severe' if (o >= 0.88 or cw >= 0.42) else 'moderate'
        explanation_parts.append(
            f"Opacidad alta ({o:.2f}), brillo {vb:.2f}, textura baja {tex:.3f}, blancura central {cw:.2f}."
        )
    # 3) Standard rule
    elif (o >= 0.68 and vb >= 0.55 and h < 0.025 and r < 0.60 and cw >= 0.28 and tex <= 0.08):
        diagnosis = 'cataracts'
        severity = 'severe' if (o >= 0.78 or cw >= 0.35) else 'moderate'
        explanation_parts.append(
            f"Opacidad elevada ({o:.2f}), brillo {vb:.2f}, blancura central {cw:.2f} con poca textura {tex:.3f}."
        )
    # 4) Fallback by central whiteness + low texture
    elif ((o >= 0.72 or cw >= 0.38) and vb >= 0.58 and r < 0.62 and tex <= 0.022):
        diagnosis = 'cataracts'
        severity = 'moderate'
        explanation_parts.append(
            f"Indicadores compatibles con cataratas: opacidad {o:.2f}/blancura {cw:.2f}, brillo {vb:.2f}, textura baja {tex:.3f}."
        )
    elif o >= opacity_minor_th and diagnosis == 'normal':
        diagnosis = 'opacidades_menores'
        severity = 'mild'
        if h >= glare_high_th:
            explanation_parts.append(f"Opacidad leve ({o:.2f}) con reflejos ({h*100:.1f}% zona brillante).")
        else:
            explanation_parts.append(f"Opacidad leve ({o:.2f}).")

    # Confidence heuristic from distances to thresholds
    conf_r = min(max((r - redness_minor_th) / (redness_conjunctivitis_th - redness_minor_th + 1e-6), 0), 1)
    conf_o = min(max((o - opacity_minor_th) / (max(0.01, 0.78) - opacity_minor_th + 1e-6), 0), 1)
    conf_w = min(max((cw - 0.20) / (max(0.21, whiteness_cataract_th) - 0.20 + 1e-6), 0), 1)
    # Reduce redness contribution to confidence to make “rojo” less dominant
    base_conf = 0.5 * conf_w + 0.40 * conf_o + 0.10 * conf_r
    # Boost if both signals are strong
    if r >= redness_conjunctivitis_th and o >= opacity_cataract_th:
        base_conf = min(1.0, base_conf + 0.2)

    # Penalize confidence if glare present (reduce impacto de reflejos)
    if h >= glare_high_th:
        # Penalización menor si la clasificación fue por opacidad muy alta
        penalty = 0.05 if 'strong_opacity_case' in locals() and strong_opacity_case else 0.15
        base_conf = max(0.0, base_conf - penalty)
        explanation_parts.append(f"Detectamos reflejos fuertes ({h*100:.1f}% píxeles muy brillantes), ajustando confianza.")

    # Co-findings: if primary is conjunctivitis, flag possible/likely cataracts based on opacity signals
    if diagnosis == 'conjunctivitis':
        if (o >= opacity_minor_th and v <= 0.28) or (cw >= whiteness_cataract_th) or (o >= 0.55 and h < glare_high_th):
            level = 'likely' if (o >= opacity_cataract_th and v <= vascular_low_th) else 'possible'
            co_findings.append({'label': 'cataracts', 'level': level, 'score': float(o)})
            explanation_parts.append(
                ("Además, se observan indicios compatibles con cataratas "
                 f"(opacidad {o:.2f}{', blancura central alta' if cw >= whiteness_cataract_th else ''}).")
            )
    # If primary is cataracts, flag possible/likely conjunctivitis based on redness/vascular
    if diagnosis == 'cataracts':
        if r >= redness_minor_th and v >= vascular_elevated_th:
            level = 'likely' if r >= redness_conjunctivitis_th else 'possible'
            co_findings.append({'label': 'conjunctivitis', 'level': level, 'score': float(r)})
            explanation_parts.append("Además, se aprecia rojez con incremento vascular compatibles con conjuntivitis.")

    # Append a short metrics summary for traceability
    explanation_parts.append(
        f"[Métricas] opacidad={o:.2f}, bordes={v:.2f}, rojez={r:.2f}, blancura={cw:.2f}, reflejos={h:.2f}."
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

    explanation = " ".join(explanation_parts) if explanation_parts else "Sin hallazgos relevantes según métricas calculadas."
    return {
        'diagnosis': diagnosis,
        'severity': severity,
        'confidence': float(max(0.0, min(1.0, base_conf))),
        'explanation': explanation,
        'recommendations': " ".join(recommendations),
        'co_findings': co_findings,
    }

class AnalyzeImageView(APIView):
    """Main endpoint for analyzing eye images (Hexagonal delegation)."""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        # Validate input
        serializer = AnalysisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        image_file = serializer.validated_data['image']

        # Feature toggles from env/settings
        from django.conf import settings as dj_settings
        enable_tta = getattr(dj_settings, 'VC_ENABLE_TTA', os.getenv('VC_ENABLE_TTA', '1'))
        enable_quality = getattr(dj_settings, 'VC_ENABLE_QUALITY', os.getenv('VC_ENABLE_QUALITY', '1'))
        p_high = getattr(dj_settings, 'VC_P_CATARACT_HIGH', float(os.getenv('VC_P_CATARACT_HIGH', '0.75')))
        p_mid = getattr(dj_settings, 'VC_P_CATARACT_MID', float(os.getenv('VC_P_CATARACT_MID', '0.55')))
        enable_tta = str(enable_tta).strip() not in ('0', 'false', 'False', '')
        enable_quality = str(enable_quality).strip() not in ('0', 'false', 'False', '')

        # Wire ports and use case
        use_case = get_analysis_use_case()
        result = use_case.execute(UploadAndAnalyzeInput(
            user_id=request.user.id,
            image_file=image_file,
            enable_tta=enable_tta,
            enable_quality=enable_quality,
            p_high=float(p_high),
            p_mid=float(p_mid),
        ))

        analysis = result['record']
        resp = {
            'analysis': AnalysisSerializer(analysis, context={'request': request}).data,
            'message': 'Análisis completado correctamente'
        }
        if result.get('processed_image_url'):
            resp['processed_image_url'] = result['processed_image_url']
            try:
                resp['analysis']['ai_raw_response']['processed_image_url'] = result['processed_image_url']
            except Exception:
                pass
        if result.get('uncertainty'):
            resp['uncertainty'] = result['uncertainty']
        if result.get('quality') is not None:
            resp['quality'] = result['quality']
        if result.get('runtime'):
            resp['runtime'] = result['runtime']
        if result.get('co_findings'):
            resp['co_findings'] = result['co_findings']
        return Response(resp, status=status.HTTP_201_CREATED)
    

class AnalysisHistoryView(generics.ListAPIView):
    """Get user's analysis history"""
    serializer_class = AnalysisHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Analysis.objects.filter(user=self.request.user)

class AnalysisDetailView(generics.RetrieveAPIView):
    """Get detailed analysis results"""
    serializer_class = AnalysisSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return Analysis.objects.filter(user=self.request.user)

class ClearHistoryView(APIView):
    """Delete all analysis history for the authenticated user (temporary utility)."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        from django.conf import settings as dj_settings
        qs = Analysis.objects.filter(user=request.user)

        # Detect storage mode for processed previews
        storage_kind = str(getattr(dj_settings, 'VC_STORAGE', 'media')).strip().lower()
        media_url = getattr(dj_settings, 'MEDIA_URL', '/media/') or '/media/'
        media_root = getattr(dj_settings, 'MEDIA_ROOT', None)

        # For Supabase deletion
        supabase_bucket = None
        supabase_client = None
        if storage_kind in ('supabase', 'supabase_storage'):
            try:
                import os as _os
                from .adapters.storage.supabase_common import create_supabase_client  # type: ignore
                supabase_bucket = _os.getenv('VC_PREVIEWS_BUCKET', 'eye-previews')
                supabase_client = create_supabase_client()
            except Exception:
                supabase_client = None

        def _delete_processed_preview(preview_url: str):
            if not preview_url:
                return
            try:
                if storage_kind in ('supabase', 'supabase_storage') and supabase_client and supabase_bucket:
                    # Expected shape: {SUPABASE_URL}/storage/v1/object/public/<bucket>/<path>
                    token = '/storage/v1/object/public/'
                    path = None
                    if token in preview_url:
                        try:
                            after = preview_url.split(token, 1)[1]
                            # after = '<bucket>/<path>'
                            parts = after.split('/', 1)
                            if len(parts) == 2:
                                bucket_in_url, rest = parts
                                if bucket_in_url == supabase_bucket:
                                    path = rest
                        except Exception:
                            path = None
                    # If path is still None, skip silently (foreign URL)
                    if path:
                        try:
                            supabase_client.storage.from_(supabase_bucket).remove([path])
                        except Exception:
                            pass
                else:
                    # Media storage: remove file if under MEDIA_URL
                    base = str(media_url)
                    url = str(preview_url)
                    idx = url.find(base)
                    if idx != -1 and media_root:
                        rel = url[idx + len(base):].lstrip('/')
                        import os as _os
                        abs_path = _os.path.join(media_root, rel)
                        try:
                            if _os.path.exists(abs_path):
                                _os.remove(abs_path)
                        except Exception:
                            pass
            except Exception:
                # Never fail whole request because of cleanup
                pass

        # Delete associated files safely, then delete DB rows
        deleted = 0
        for analysis in qs.iterator():
            # Remove uploaded image file
            try:
                if getattr(analysis, 'image', None):
                    analysis.image.delete(save=False)
            except Exception:
                pass
            # Remove processed preview if any
            try:
                raw = getattr(analysis, 'ai_raw_response', None) or {}
                preview = raw.get('processed_image_url') if isinstance(raw, dict) else None
                if isinstance(preview, str) and preview:
                    _delete_processed_preview(preview)
            except Exception:
                pass
            deleted += 1
        # Bulk delete rows
        qs.delete()
        return Response({'message': 'Historial eliminado correctamente', 'deleted': deleted}, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def download_analysis_pdf(request, analysis_id):
    """Generate and download a professional PDF report for an analysis with branding and extended metrics."""
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)

    # Extract extra (runtime / uncertainty / quality) if present in ai_raw_response
    ai_raw = getattr(analysis, 'ai_raw_response', None) or {}
    onnx_probs = ai_raw.get('onnx') or {}
    uncertainty = ai_raw.get('uncertainty') or {}
    quality = ai_raw.get('quality') or {}
    runtime = ai_raw.get('runtime') or {}

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=50,
        rightMargin=50,
        topMargin=90,
        bottomMargin=60,
        title="Reporte VisionCare"
    )
    styles = getSampleStyleSheet()
    styles['Title'].fontSize = 20
    styles['Title'].leading = 24
    styles['Heading2'].spaceBefore = 12
    styles['Heading2'].spaceAfter = 6
    story = []

    def build_table(data, header_bg=colors.Color(0.15,0.25,0.55), header_text=colors.whitesmoke):
        tbl = Table(data, colWidths=[160, 330])
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), header_bg),
            ('TEXTCOLOR', (0,0), (-1,0), header_text),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 11),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('BOX', (0,0), (-1,-1), 0.75, colors.grey),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.Color(0.97,0.97,0.99)])
        ]))
        return tbl

    story.append(Paragraph("Reporte de Análisis VisionCare", styles['Title']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Análisis asistido por IA. Este documento no reemplaza una evaluación médica profesional.", styles['Normal']))
    story.append(Spacer(1, 14))

    full_name = f"{analysis.user.first_name} {analysis.user.last_name}".strip() or analysis.user.email
    patient_info = [
        ["INFORMACIÓN DEL PACIENTE", ""],
        ["Nombre completo", full_name],
        ["Correo", analysis.user.email],
        ["Edad", str(getattr(analysis.user, 'age', '—') or '—')],
        ["Cédula", getattr(analysis.user, 'cedula', '') or '—'],
        ["País", getattr(analysis.user, 'country', '') or '—'],
        ["Estado / Provincia", getattr(analysis.user, 'state', '') or '—'],
        ["Ciudad", getattr(analysis.user, 'city', '') or '—'],
        ["Fecha del análisis", analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')],
        ["ID del análisis", str(analysis.id)],
    ]
    story.append(build_table(patient_info))
    story.append(Spacer(1, 16))

    cataracts_prob = onnx_probs.get('cataracts')
    vascular = analysis.opencv_vascular_density
    results_rows = [
        ["RESULTADOS DEL MODELO", ""],
        ["Diagnóstico principal", analysis.get_diagnosis_display()],
        ["Severidad", analysis.get_severity_display()],
        ["Confianza (clasificador)", f"{analysis.confidence_score:.2%}"],
        ["Rojez (OpenCV)", f"{analysis.opencv_redness_score:.3f}"],
        ["Opacidad (OpenCV)", f"{analysis.opencv_opacity_score:.3f}"],
    ]
    if vascular is not None:
        results_rows.append(["Densidad vascular (OpenCV)", f"{vascular:.3f}"])
    if isinstance(cataracts_prob, (int,float)):
        results_rows.append(["Prob. de cataratas (ONNX)", f"{cataracts_prob:.2%}"])
    story.append(build_table(results_rows, header_bg=colors.Color(0.05,0.45,0.65)))
    story.append(Spacer(1, 16))

    extra_sections = []
    if quality:
        extra_sections.extend([
            ["Calidad de imagen", ""],
            ["Puntaje de calidad", f"{quality.get('quality_score',0):.2f}"],
            ["Estado", 'buena' if quality.get('quality_flag') == 'ok' else ('baja' if quality.get('quality_flag') == 'low' else quality.get('quality_flag','—'))],
            ["Brillo medio", f"{quality.get('mean_brightness',0):.3f}"],
        ])
    if uncertainty:
        extra_sections.append(["Incertidumbre / Consistencia", ""])
        if 'mean_top_prob' in uncertainty:
            extra_sections.append(["Prob. media top", f"{uncertainty['mean_top_prob']:.2%}"])
        if 'entropy' in uncertainty:
            extra_sections.append(["Entropía", f"{uncertainty['entropy']:.4f}"])
        if 'entropy_normalized' in uncertainty:
            extra_sections.append(["Entropía normalizada", f"{uncertainty['entropy_normalized']:.4f}"])
    if runtime:
        extra_sections.append(["Ejecución", ""])
        if 'model_count' in runtime:
            extra_sections.append(["Número de modelos", str(runtime['model_count'])])
        if runtime.get('providers'):
            extra_sections.append(["Proveedores", ', '.join(runtime.get('providers', []))])
    if extra_sections:
        story.append(build_table([["MÉTRICAS ADICIONALES",""], *extra_sections[1:]], header_bg=colors.Color(0.25,0.45,0.15)))
        story.append(Spacer(1, 16))

    if analysis.ai_analysis_text:
        story.append(Paragraph("Análisis de IA", styles['Heading2']))
        story.append(Paragraph(analysis.ai_analysis_text, styles['Normal']))
        story.append(Spacer(1, 10))
    if analysis.recommendations:
        story.append(Paragraph("Recomendaciones", styles['Heading2']))
        story.append(Paragraph(analysis.recommendations, styles['Normal']))
        story.append(Spacer(1, 10))
    if analysis.medical_advice:
        story.append(Paragraph("Consejo médico", styles['Heading2']))
        story.append(Paragraph(analysis.medical_advice, styles['Normal']))
        story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Descargo de responsabilidad:</b> Este reporte es generado automáticamente y no sustituye una evaluación clínica presencial. Ante síntomas persistentes consulte a un profesional de la salud.", styles['Normal']))

    logo_path = os.path.join(settings.BASE_DIR, 'frontend', 'public', 'logo-eye.png')
    alt_logo_path = os.path.join(settings.BASE_DIR, 'frontend', 'public', 'Logo_inicio.png')
    def _header_footer(c, doc_obj):
        c.saveState()
        c.setFillColorRGB(0.05,0.25,0.55)
        c.rect(0, letter[1]-70, letter[0], 70, fill=1, stroke=0)
        img_used = logo_path if os.path.exists(logo_path) else (alt_logo_path if os.path.exists(alt_logo_path) else None)
        if img_used:
            try:
                c.drawImage(img_used, 40, letter[1]-62, width=60, height=54, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
        c.setFillColor(colors.whitesmoke)
        c.setFont('Helvetica-Bold', 16)
        c.drawString(110, letter[1]-38, 'VisionCare Web')
        c.setFont('Helvetica', 8.5)
        c.drawString(110, letter[1]-52, 'Reporte clínico asistido por IA')
        c.setFillColor(colors.grey)
        c.setFont('Helvetica', 8)
        c.drawCentredString(letter[0]/2.0, 40, f"VisionCare Web • Reporte generado: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} • Página {doc_obj.page}")
        c.restoreState()

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="visioncare_analysis_{analysis.id}.pdf"'
    return response

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def runtime_info(request):
    """Expose ONNX runtime and model discovery info for diagnostics."""
    try:
        info = get_runtime_debug()
        return Response(info, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
