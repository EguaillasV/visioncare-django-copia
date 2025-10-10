from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from . import views

app_name = 'vision_app'

@api_view(['GET'])
@permission_classes([AllowAny])
def api_test(request):
    """Test endpoint to check if API is working"""
    return Response({
        'message': 'VisionCare Django API is working!',
        'version': '1.0.0',
        'endpoints_available': True
    })

urlpatterns = [
    # Test endpoint
    path('test/', api_test, name='api_test'),
    
    # Authentication endpoints
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/profile/', views.ProfileView.as_view(), name='profile'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    path('auth/avatar/', views.UploadAvatarView.as_view(), name='upload_avatar'),
    
    # Analysis endpoints
    path('analyze-image/', views.AnalyzeImageView.as_view(), name='analyze_image'),
    path('history/', views.AnalysisHistoryView.as_view(), name='analysis_history'),
    path('history/clear/', views.ClearHistoryView.as_view(), name='clear_history'),
    path('analysis/<uuid:pk>/', views.AnalysisDetailView.as_view(), name='analysis_detail'),
    path('download-analysis/<uuid:analysis_id>/', views.download_analysis_pdf, name='download_analysis_pdf'),
    path('runtime-info/', views.runtime_info, name='runtime_info'),
]