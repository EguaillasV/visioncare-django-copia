import os
import cv2
import numpy as np
import time
from datetime import datetime
from PIL import Image
from io import BytesIO
import openai
import base64
from django.conf import settings
from django.http import HttpResponse, FileResponse
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
import tempfile

from .models import User, Analysis, AnalysisSession
from .serializers import (
    UserRegistrationSerializer, UserLoginSerializer, UserProfileSerializer,
    AnalysisSerializer, AnalysisCreateSerializer, AnalysisHistorySerializer
)

# Set OpenAI API key
openai.api_key = settings.OPENAI_API_KEY

class RegisterView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': UserProfileSerializer(user).data,
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
            'message': 'Login successful',
            'user': UserProfileSerializer(user).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        })

class ProfileView(generics.RetrieveUpdateAPIView):
    """User profile endpoint"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def openai_health(request):
    """Minimal health check for OpenAI API availability and quota."""
    if not settings.OPENAI_API_KEY:
        return Response({
            'ok': False,
            'status': 'missing_api_key',
            'message': 'OPENAI_API_KEY is not configured.'
        }, status=200)

    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        # Minimal non-image prompt to reduce cost
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":"Say OK"}],
            max_tokens=2
        )
        text = resp.choices[0].message.content.strip().upper()
        return Response({
            'ok': True,
            'status': 'reachable',
            'reply': text
        })
    except Exception as e:
        s = str(e)
        status_code = 429 if 'insufficient_quota' in s.lower() or '429' in s else 401 if '401' in s else 500
        status_text = 'insufficient_quota' if status_code == 429 else 'unauthorized' if status_code == 401 else 'error'
        return Response({
            'ok': False,
            'status': status_text,
            'error': s
        }, status=200)

# OpenCV Image Analysis Functions
def enhance_image_quality(image_array):
    """Enhance image quality using OpenCV"""
    # Convert to grayscale for processing
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Convert back to RGB
    enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
    
    return enhanced_rgb

def detect_eye_region(image_array):
    """Detect eye region in the image"""
    gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    
    # Load OpenCV's pre-trained eye classifier
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')
    
    eyes = eye_cascade.detectMultiScale(gray, 1.1, 4)
    
    if len(eyes) > 0:
        # Return the largest detected eye region
        largest_eye = max(eyes, key=lambda e: e[2] * e[3])
        x, y, w, h = largest_eye
        return image_array[y:y+h, x:x+w]
    
    # If no eye detected, return center portion of image
    h, w = image_array.shape[:2]
    center_x, center_y = w // 2, h // 2
    crop_size = min(w, h) // 2
    
    start_x = max(0, center_x - crop_size // 2)
    end_x = min(w, center_x + crop_size // 2)
    start_y = max(0, center_y - crop_size // 2)
    end_y = min(h, center_y + crop_size // 2)
    
    return image_array[start_y:end_y, start_x:end_x]

def analyze_eye_features(eye_region):
    """Analyze eye features using OpenCV"""
    # Calculate redness score
    red_channel = eye_region[:, :, 0].astype(np.float32)
    green_channel = eye_region[:, :, 1].astype(np.float32)
    blue_channel = eye_region[:, :, 2].astype(np.float32)
    
    # Redness calculation
    redness_score = np.mean(red_channel / (green_channel + blue_channel + 1))
    
    # Opacity/cloudiness calculation
    gray = cv2.cvtColor(eye_region, cv2.COLOR_RGB2GRAY)
    opacity_score = np.std(gray) / 255.0  # Normalized standard deviation
    
    # Vascular density (edge detection)
    edges = cv2.Canny(gray, 50, 150)
    vascular_density = np.sum(edges > 0) / edges.size
    
    return {
        'redness_score': float(redness_score),
        'opacity_score': float(1.0 - opacity_score),  # Lower std = more opaque
        'vascular_density': float(vascular_density)
    }

def _rule_based_ai(opencv_results, reason="rule-based fallback"):
    """Heuristic diagnosis using OpenCV metrics when OpenAI is unavailable."""
    redness = opencv_results.get('redness_score', 0.0)
    opacity = opencv_results.get('opacity_score', 0.0)
    vascular = opencv_results.get('vascular_density', 0.0)

    # Simple thresholds (tunable)
    if opacity >= 0.6:
        diagnosis = 'cataracts'
        severity = 'moderate' if opacity < 0.8 else 'severe'
        confidence = min(0.9, 0.5 + (opacity - 0.6))
        explanation = (
            f"Rule-based analysis suggests cataracts due to higher opacity score ({opacity:.3f})."
        )
        recommendations = (
            "Schedule an appointment with an ophthalmologist to evaluate lens opacity."
        )
    elif redness >= 0.25 and vascular >= 0.05:
        diagnosis = 'conjunctivitis'
        severity = 'mild' if redness < 0.35 else 'moderate'
        confidence = min(0.85, 0.5 + (redness - 0.25))
        explanation = (
            f"Rule-based analysis suggests conjunctivitis due to elevated redness ({redness:.3f}) "
            f"and vascular density ({vascular:.3f})."
        )
        recommendations = (
            "Maintain eye hygiene, avoid touching eyes, and consult a healthcare provider if symptoms persist."
        )
    elif redness >= 0.18:
        diagnosis = 'redness_minor'
        severity = 'mild'
        confidence = 0.6
        explanation = (
            f"Mild eye redness detected (score {redness:.3f})."
        )
        recommendations = (
            "Consider rest, artificial tears, and monitor symptoms. Seek medical advice if worsening."
        )
    else:
        diagnosis = 'normal'
        severity = 'normal'
        confidence = 0.7
        explanation = (
            "No significant signs of cataracts or conjunctivitis detected by OpenCV metrics."
        )
        recommendations = (
            "Maintain regular eye care. If you have symptoms, consult a healthcare professional."
        )

    explanation = f"{explanation} (AI {reason})."
    return {
        "diagnosis": diagnosis,
        "severity": severity,
        "confidence": float(confidence),
        "explanation": explanation,
        "recommendations": recommendations,
    }


def analyze_with_openai(image_array, opencv_results):
    """Analyze eye image using OpenAI Vision API with graceful degradation."""
    # If no API key, fall back immediately
    if not settings.OPENAI_API_KEY:
        return _rule_based_ai(opencv_results, reason="disabled or missing API key")

    try:
        # Convert image to base64
        pil_image = Image.fromarray(image_array)
        buffer = BytesIO()
        pil_image.save(buffer, format='JPEG')
        buffer.seek(0)
        b64_image = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Create a detailed prompt for medical analysis
        prompt = f"""You are a medical AI assistant specializing in ophthalmology. Analyze this eye image for potential conditions.

OpenCV Analysis Results:
- Redness Score: {opencv_results['redness_score']:.3f}
- Opacity Score: {opencv_results['opacity_score']:.3f} 
- Vascular Density: {opencv_results['vascular_density']:.3f}

Please provide:
1. Primary diagnosis (normal, conjunctivitis, cataracts, opacidades_menores, redness_minor)
2. Severity level (normal, mild, moderate, severe)
3. Confidence score (0-1)
4. Brief medical explanation
5. Conservative recommendations

Respond in JSON format:
{{
    "diagnosis": "diagnosis_name",
    "severity": "severity_level", 
    "confidence": 0.85,
    "explanation": "Brief medical explanation",
    "recommendations": "Conservative medical advice"
}}"""

        # Call OpenAI API
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        ai_response = response.choices[0].message.content
        
        # Try to parse JSON response
        import json
        try:
            parsed_response = json.loads(ai_response)
            return parsed_response
        except json.JSONDecodeError:
            # Fallback response if JSON parsing fails
            return _rule_based_ai(opencv_results, reason="fallback due to unparseable AI response")
            
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        reason = "quota exceeded" if "insufficient_quota" in str(e).lower() or "429" in str(e) else "temporary AI error"
        return _rule_based_ai(opencv_results, reason=reason)

class AnalyzeImageView(APIView):
    """Main endpoint for analyzing eye images"""
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        start_time = time.time()
        
        # Validate input
        serializer = AnalysisCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            # Load and process image
            image_file = serializer.validated_data['image']
            
            # Convert to OpenCV format
            pil_image = Image.open(image_file)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            image_array = np.array(pil_image)
            
            # Enhance image quality
            enhanced_image = enhance_image_quality(image_array)
            
            # Detect and extract eye region
            eye_region = detect_eye_region(enhanced_image)
            
            # Analyze eye features with OpenCV
            opencv_results = analyze_eye_features(eye_region)
            
            # Analyze with OpenAI
            ai_results = analyze_with_openai(eye_region, opencv_results)
            
            # Calculate final confidence and diagnosis
            final_confidence = (opencv_results['redness_score'] * 0.3 + 
                              opencv_results['opacity_score'] * 0.3 +
                              ai_results['confidence'] * 0.4)
            
            analysis_duration = time.time() - start_time
            
            # Create analysis record
            analysis = Analysis.objects.create(
                user=request.user,
                image=image_file,
                diagnosis=ai_results['diagnosis'],
                severity=ai_results['severity'],
                confidence_score=final_confidence,
                opencv_redness_score=opencv_results['redness_score'],
                opencv_opacity_score=opencv_results['opacity_score'],
                opencv_vascular_density=opencv_results['vascular_density'],
                ai_analysis_text=ai_results['explanation'],
                ai_confidence=ai_results['confidence'],
                ai_raw_response=ai_results,
                recommendations=ai_results['recommendations'],
                medical_advice=self.generate_conservative_advice(ai_results),
                analysis_duration=analysis_duration
            )
            
            # Return results
            return Response({
                'analysis': AnalysisSerializer(analysis, context={'request': request}).data,
                'message': 'Analysis completed successfully'
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                'error': f'Analysis failed: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def generate_conservative_advice(self, ai_results):
        """Generate conservative medical advice"""
        base_advice = "This is an AI-powered analysis and should not replace professional medical diagnosis. "
        
        if ai_results['diagnosis'] in ['conjunctivitis', 'cataracts']:
            return base_advice + "Please consult with an ophthalmologist or healthcare provider for proper evaluation and treatment."
        elif ai_results['diagnosis'] in ['opacidades_menores', 'redness_minor']:
            return base_advice + "Consider monitoring the condition and consult a healthcare provider if symptoms persist or worsen."
        else:
            return base_advice + "If you have any concerns about your eye health, please consult with a healthcare professional."

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

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def download_analysis_pdf(request, analysis_id):
    """Generate and download PDF report for analysis"""
    analysis = get_object_or_404(Analysis, id=analysis_id, user=request.user)
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title = Paragraph("VisionCare Analysis Report", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    # Patient info
    patient_info = [
        ['Patient:', f"{analysis.user.first_name} {analysis.user.last_name}"],
        ['Email:', analysis.user.email],
        ['Analysis Date:', analysis.created_at.strftime('%Y-%m-%d %H:%M:%S')],
        ['Analysis ID:', str(analysis.id)]
    ]
    
    patient_table = Table(patient_info, colWidths=[2*72, 4*72])
    patient_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(patient_table)
    story.append(Spacer(1, 12))
    
    # Analysis results
    results_data = [
        ['Diagnosis:', analysis.get_diagnosis_display()],
        ['Severity:', analysis.get_severity_display()],
        ['Confidence Score:', f"{analysis.confidence_score:.2%}"],
        ['OpenCV Redness Score:', f"{analysis.opencv_redness_score:.3f}"],
        ['OpenCV Opacity Score:', f"{analysis.opencv_opacity_score:.3f}"],
        ['AI Confidence:', f"{analysis.ai_confidence:.2%}"]
    ]
    
    results_table = Table(results_data, colWidths=[2*72, 4*72])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(results_table)
    story.append(Spacer(1, 12))
    
    # AI Analysis
    if analysis.ai_analysis_text:
        story.append(Paragraph("AI Analysis:", styles['Heading2']))
        story.append(Paragraph(analysis.ai_analysis_text, styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Recommendations
    if analysis.recommendations:
        story.append(Paragraph("Recommendations:", styles['Heading2']))
        story.append(Paragraph(analysis.recommendations, styles['Normal']))
        story.append(Spacer(1, 12))
    
    # Medical advice
    if analysis.medical_advice:
        story.append(Paragraph("Medical Advice:", styles['Heading2']))
        story.append(Paragraph(analysis.medical_advice, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    # Return PDF response
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="visioncare_analysis_{analysis.id}.pdf"'
    
    return response
