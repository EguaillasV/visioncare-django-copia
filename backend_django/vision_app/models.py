import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from PIL import Image
import os

class User(AbstractUser):
    """Custom User model for VisionCare"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    # Profile picture
    avatar = models.ImageField(upload_to='avatars/%Y/%m/%d/', null=True, blank=True)
    # Additional profile fields
    age = models.PositiveIntegerField(null=True, blank=True)
    cedula = models.CharField(max_length=32, unique=True, null=True, blank=True)
    GENDER_CHOICES = [
        ('male', 'Masculino'),
        ('female', 'Femenino'),
        ('other', 'Otro'),
        ('na', 'Prefiero no decir')
    ]
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    phone = models.CharField(max_length=32, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    # Location fields
    country = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    # Medical information
    BLOOD_TYPES = [
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
        ('SN', 'S/N'),  # Sin información
    ]
    blood_type = models.CharField(max_length=3, choices=BLOOD_TYPES, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    height_m = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

class Analysis(models.Model):
    """Model to store eye analysis results"""
    DIAGNOSIS_CHOICES = [
        ('normal', 'Normal'),
        ('conjunctivitis', 'Conjunctivitis'),
        ('cataracts', 'Cataracts'),
        ('opacidades_menores', 'Opacidades Menores'),
        ('redness_minor', 'Redness Minor'),
        ('unknown', 'Unknown/Inconclusive'),
    ]
    
    SEVERITY_CHOICES = [
        ('normal', 'Normal'),
        ('mild', 'Mild'),
        ('moderate', 'Moderate'),
        ('severe', 'Severe'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    
    # Image data
    image = models.ImageField(
        upload_to='eye_images/%Y/%m/%d/',
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp'])]
    )
    image_size = models.PositiveIntegerField(null=True, blank=True)  # In bytes
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)
    
    # Analysis results
    diagnosis = models.CharField(max_length=50, choices=DIAGNOSIS_CHOICES, default='unknown')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='normal')
    confidence_score = models.FloatField(default=0.0)  # 0.0 to 1.0
    
    # OpenCV Analysis Results
    opencv_redness_score = models.FloatField(default=0.0)
    opencv_opacity_score = models.FloatField(default=0.0)
    opencv_vascular_density = models.FloatField(default=0.0)
    
    # AI Analysis Results
    ai_analysis_text = models.TextField(blank=True)
    ai_confidence = models.FloatField(default=0.0)
    ai_raw_response = models.JSONField(default=dict, blank=True)
    
    # Medical recommendations
    recommendations = models.TextField(blank=True)
    medical_advice = models.TextField(blank=True)
    
    # Metadata
    analysis_duration = models.FloatField(default=0.0)  # Time in seconds
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['diagnosis']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Analysis {self.id} - {self.user.email} - {self.diagnosis}"
    
    def save(self, *args, **kwargs):
        if self.image:
            # Get image metadata
            self.image_size = self.image.size
            
            # Open image to get dimensions
            try:
                with Image.open(self.image) as img:
                    self.image_width, self.image_height = img.size
            except Exception:
                pass
        
        super().save(*args, **kwargs)
    
    @property
    def image_url(self):
        """Get the full URL of the image"""
        if self.image:
            return self.image.url
        return None
    
    @property
    def is_normal(self):
        """Check if the analysis result is normal"""
        return self.diagnosis == 'normal'
    
    @property
    def requires_medical_attention(self):
        """Check if the condition requires medical attention"""
        return self.diagnosis in ['conjunctivitis', 'cataracts'] or self.severity in ['moderate', 'severe']

class AnalysisSession(models.Model):
    """Model to track analysis sessions for rate limiting and monitoring"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    session_start = models.DateTimeField(auto_now_add=True)
    session_end = models.DateTimeField(null=True, blank=True)
    analyses_count = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"Session {self.id} - {self.user.email} - {self.analyses_count} analyses"
