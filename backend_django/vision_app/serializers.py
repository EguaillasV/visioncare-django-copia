from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Analysis, AnalysisSession

class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'password', 'password_confirm')
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm', None)
        user = User.objects.create_user(**validated_data)
        return user

class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(username=email, password=password)  # Using email as username
            if not user:
                raise serializers.ValidationError('Invalid email or password')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled')
            attrs['user'] = user
        else:
            raise serializers.ValidationError('Email and password are required')
        
        return attrs

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile information"""
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'first_name', 'last_name', 'created_at')
        read_only_fields = ('id', 'email', 'created_at')

class AnalysisSerializer(serializers.ModelSerializer):
    """Serializer for eye analysis results"""
    user = UserProfileSerializer(read_only=True)
    image_url = serializers.SerializerMethodField()
    requires_medical_attention = serializers.BooleanField(read_only=True)
    is_normal = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Analysis
        fields = [
            'id', 'user', 'image', 'image_url', 'image_size', 
            'image_width', 'image_height', 'diagnosis', 'severity',
            'confidence_score', 'opencv_redness_score', 'opencv_opacity_score',
            'opencv_vascular_density', 'ai_analysis_text', 'ai_confidence',
            'recommendations', 'medical_advice', 'analysis_duration',
            'created_at', 'updated_at', 'requires_medical_attention', 'is_normal'
        ]
        read_only_fields = [
            'id', 'user', 'diagnosis', 'severity', 'confidence_score',
            'opencv_redness_score', 'opencv_opacity_score', 'opencv_vascular_density',
            'ai_analysis_text', 'ai_confidence', 'recommendations', 'medical_advice',
            'analysis_duration', 'created_at', 'updated_at', 'image_size',
            'image_width', 'image_height', 'requires_medical_attention', 'is_normal'
        ]
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

class AnalysisCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new analysis"""
    class Meta:
        model = Analysis
        fields = ['image']
    
    def validate_image(self, value):
        # Validate file size (10MB max)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image file size cannot exceed 10MB")
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Only JPEG, PNG, and WEBP images are allowed")
        
        return value

class AnalysisHistorySerializer(serializers.ModelSerializer):
    """Simplified serializer for analysis history"""
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Analysis
        fields = [
            'id', 'image_url', 'diagnosis', 'severity', 'confidence_score',
            'created_at', 'requires_medical_attention', 'is_normal'
        ]
    
    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None

class AnalysisSessionSerializer(serializers.ModelSerializer):
    """Serializer for analysis sessions"""
    user = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = AnalysisSession
        fields = ['id', 'user', 'session_start', 'session_end', 'analyses_count']
        read_only_fields = ['id', 'user', 'session_start', 'session_end', 'analyses_count']