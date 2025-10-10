from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, Analysis, AnalysisSession
import re
from django.core.files.storage import default_storage
from django.conf import settings


def validar_cedula_ecuador(cedula: str) -> bool:
    """Valida cédula ecuatoriana de 10 dígitos con dígito verificador."""
    if not cedula or not cedula.isdigit() or len(cedula) != 10:
        return False
    provincia = int(cedula[0:2])
    if not (0 <= provincia <= 24 or provincia == 30):
        return False
    # tercer dígito < 6 para personas naturales
    if int(cedula[2]) >= 6:
        return False
    coef = [2, 1, 2, 1, 2, 1, 2, 1, 2]
    total = 0
    for i in range(9):
        prod = int(cedula[i]) * coef[i]
        if prod >= 10:
            prod -= 9
        total += prod
    verificador = (10 - (total % 10)) % 10
    return verificador == int(cedula[9])

class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer para registro de usuario con campos adicionales"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    # Nuevos campos requeridos
    age = serializers.IntegerField(required=True, min_value=1, max_value=120)
    cedula = serializers.CharField(required=True, max_length=32)
    gender = serializers.ChoiceField(required=True, choices=User.GENDER_CHOICES)
    phone = serializers.CharField(required=True, max_length=32)
    address = serializers.CharField(required=True)
    country = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    state = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    
    class Meta:
        model = User
        fields = (
            'email', 'username', 'first_name', 'last_name',
            'password', 'password_confirm',
            'age', 'cedula', 'gender', 'phone', 'address', 'country', 'state', 'city'
        )
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        # Normalización
        attrs['first_name'] = (attrs.get('first_name') or '').strip()
        attrs['last_name'] = (attrs.get('last_name') or '').strip()
        attrs['email'] = (attrs.get('email') or '').strip().lower()
        attrs['username'] = (attrs.get('username') or '').strip()
        attrs['cedula'] = (attrs.get('cedula') or '').strip()
        attrs['phone'] = (attrs.get('phone') or '').strip()
        attrs['address'] = (attrs.get('address') or '').strip()
        # Validaciones específicas
        if not validar_cedula_ecuador(attrs['cedula']):
            raise serializers.ValidationError({'cedula': 'La cédula ecuatoriana no es válida'})
        # Teléfono Ecuador: 09XXXXXXXX (local) o +5939XXXXXXXX (internacional)
        # Ampliar validación: aceptar E.164 que empiece por + y 8-15 dígitos (o formato local de Ecuador)
        if not re.fullmatch(r"(?:\+\d{8,15}|09\d{8}|\+5939\d{8})", attrs['phone']):
            raise serializers.ValidationError({'phone': 'Formato de teléfono inválido. Use +[código][número] o 09XXXXXXXX en Ecuador'})
        # Unicidad amigable antes de intentar insertar (evita 500 por IntegrityError)
        if attrs['email'] and User.objects.filter(email__iexact=attrs['email']).exists():
            raise serializers.ValidationError({'email': 'Este correo ya está registrado'})
        if attrs['username'] and User.objects.filter(username__iexact=attrs['username']).exists():
            raise serializers.ValidationError({'username': 'Este usuario ya está registrado'})
        if attrs['cedula'] and User.objects.filter(cedula=attrs['cedula']).exists():
            raise serializers.ValidationError({'cedula': 'Esta cédula ya está registrada'})
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
    avatar_url = serializers.SerializerMethodField()
    class Meta:
        model = User
        fields = (
            'id', 'email', 'username', 'first_name', 'last_name',
            'age', 'cedula', 'gender', 'phone', 'address', 'country', 'state', 'city',
            'blood_type', 'weight_kg', 'height_m',
            'avatar_url', 'created_at'
        )
        read_only_fields = ('id', 'created_at')

    def get_avatar_url(self, obj):
        if not getattr(obj, 'avatar', None):
            return None
        request = self.context.get('request')

        # In Supabase mode, avoid exists() check which can be slow or unreliable
        storage_kind = str(getattr(settings, 'VC_STORAGE', 'media')).strip().lower()
        if storage_kind not in ('supabase', 'supabase_storage'):
            # Local media mode: avoid returning broken links
            try:
                name = getattr(obj.avatar, 'name', None)
                if not name or not default_storage.exists(name):
                    return None
            except Exception:
                return None

        url = getattr(obj.avatar, 'url', None)
        if not url:
            return None
        # If storage returns an absolute URL (e.g., Supabase), don't wrap it again
        if str(url).startswith(('http://', 'https://')):
            base = url
        else:
            base = request.build_absolute_uri(url) if request else url
        # Cache-busting using last update timestamp (skip if URL already has query like signed URLs)
        try:
            version = int(obj.updated_at.timestamp()) if getattr(obj, 'updated_at', None) else None
        except Exception:
            version = None
        if version is not None and '?' not in base:
            return f"{base}?v={version}"
        return base

    def validate_email(self, value):
        value = (value or '').strip().lower()
        if not value:
            raise serializers.ValidationError('El correo no puede estar vacío')
        qs = User.objects.filter(email=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Este correo ya está en uso')
        return value

    def update(self, instance, validated_data):
        # Normalize fields
        if 'email' in validated_data:
            validated_data['email'] = (validated_data['email'] or '').strip().lower()
        if 'first_name' in validated_data and validated_data['first_name'] is not None:
            validated_data['first_name'] = validated_data['first_name'].strip()
        if 'last_name' in validated_data and validated_data['last_name'] is not None:
            validated_data['last_name'] = validated_data['last_name'].strip()
        if 'username' in validated_data and validated_data['username'] is not None:
            validated_data['username'] = validated_data['username'].strip()
        return super().update(instance, validated_data)

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
            url = obj.image.url
            if not url:
                return None
            # Avoid double-wrapping absolute Supabase URLs
            if str(url).startswith(('http://', 'https://')):
                return url
            request = self.context.get('request')
            return request.build_absolute_uri(url) if request else url
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
        
        # Validate file type: allow common MIME variants and fallback to extension if needed
        allowed_types = {
            'image/jpeg', 'image/jpg', 'image/pjpeg', 'image/jfif',
            'image/png', 'image/x-png',
            'image/webp',
        }
        ctype = getattr(value, 'content_type', None)
        ok_type = bool(ctype and ctype.lower() in allowed_types)
        if not ok_type:
            # Fallback a la extensión del archivo cuando el navegador no envía un Content-Type estándar
            name = getattr(value, 'name', '')
            ext = (name.rsplit('.', 1)[-1] or '').lower()
            if ext in {'jpg', 'jpeg', 'png', 'webp'}:
                ok_type = True
        if not ok_type:
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
        """Return a lightweight preview URL when available; fallback to original image.

        - If ai_raw_response.processed_image_url exists, use it (usually a small JPEG we generate).
        - If it's a relative path, make it absolute using request.
        - Otherwise, use the original ImageField URL.
        """
        # 1) Prefer processed preview saved during analysis
        try:
            raw = obj.ai_raw_response or {}
            preview = raw.get('processed_image_url')
            if preview:
                if isinstance(preview, str) and preview.startswith(('http://', 'https://')):
                    return preview
                request = self.context.get('request')
                if request and isinstance(preview, str):
                    return request.build_absolute_uri(preview)
                return preview
        except Exception:
            pass

        # 2) Fallback to original uploaded image
        if getattr(obj, 'image', None):
            try:
                url = obj.image.url
            except Exception:
                url = None
            if not url:
                return None
            if str(url).startswith(('http://', 'https://')):
                return url
            request = self.context.get('request')
            return request.build_absolute_uri(url) if request else url
        return None

class AnalysisSessionSerializer(serializers.ModelSerializer):
    """Serializer for analysis sessions"""
    user = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = AnalysisSession
        fields = ['id', 'user', 'session_start', 'session_end', 'analyses_count']
        read_only_fields = ['id', 'user', 'session_start', 'session_end', 'analyses_count']


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer to change user password"""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context['request'].user
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        new_password_confirm = attrs.get('new_password_confirm')

        if not user.check_password(old_password):
            raise serializers.ValidationError({'old_password': 'Contraseña actual incorrecta'})
        if new_password != new_password_confirm:
            raise serializers.ValidationError({'new_password_confirm': 'Las contraseñas no coinciden'})
        if old_password == new_password:
            raise serializers.ValidationError({'new_password': 'La nueva contraseña no puede ser igual a la actual'})
        return attrs