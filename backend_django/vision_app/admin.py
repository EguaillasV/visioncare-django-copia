from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Analysis, AnalysisSession

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin"""
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'username')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Analysis)
class AnalysisAdmin(admin.ModelAdmin):
    """Analysis admin"""
    list_display = ('id', 'user_name', 'diagnosis', 'severity', 'confidence_score', 'created_at', 'image_preview')
    list_filter = ('diagnosis', 'severity', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'diagnosis')
    readonly_fields = ('id', 'created_at', 'updated_at', 'image_preview', 'analysis_duration')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('id', 'user', 'created_at', 'updated_at')
        }),
        ('Image', {
            'fields': ('image', 'image_preview', 'image_size', 'image_width', 'image_height')
        }),
        ('Analysis Results', {
            'fields': ('diagnosis', 'severity', 'confidence_score', 'analysis_duration')
        }),
        ('OpenCV Results', {
            'fields': ('opencv_redness_score', 'opencv_opacity_score', 'opencv_vascular_density')
        }),
        ('AI Analysis', {
            'fields': ('ai_analysis_text', 'ai_confidence', 'ai_raw_response')
        }),
        ('Medical Info', {
            'fields': ('recommendations', 'medical_advice')
        }),
    )
    
    def user_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"
    user_name.short_description = 'User'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 200px;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = 'Image Preview'

@admin.register(AnalysisSession)
class AnalysisSessionAdmin(admin.ModelAdmin):
    """Analysis Session admin"""
    list_display = ('id', 'user', 'ip_address', 'session_start', 'analyses_count')
    list_filter = ('session_start',)
    search_fields = ('user__email', 'ip_address')
    readonly_fields = ('id', 'session_start', 'session_end')
    ordering = ('-session_start',)
