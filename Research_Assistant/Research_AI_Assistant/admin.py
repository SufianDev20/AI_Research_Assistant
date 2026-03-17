"""
Django admin configuration for Research AI Assistant models.
Provides interface for monitoring OpenRouter model performance.
"""

from django.contrib import admin
from django.utils.safestring import mark_safe
from django.db.models import Count, Avg
from .models import QueryLog, ModelPerformance, ResponseLog, ModelReliability


@admin.register(QueryLog)
class QueryLogAdmin(admin.ModelAdmin):
    """Admin interface for query logs."""
    
    list_display = ['query_text_short', 'ranking_mode', 'result_count', 'created_at']
    list_filter = ['ranking_mode', 'created_at']
    search_fields = ['query_text']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
    
    def query_text_short(self, obj):
        return obj.query_text[:50] + '...' if len(obj.query_text) > 50 else obj.query_text
    query_text_short.short_description = 'Query'


@admin.register(ModelPerformance)
class ModelPerformanceAdmin(admin.ModelAdmin):
    """Admin interface for model performance tracking."""
    
    list_display = [
        'model_name', 'success_rate', 'reliability_score', 
        'avg_response_time', 'total_requests', 'consecutive_failures', 
        'is_active', 'last_success'
    ]
    list_filter = ['is_active', 'last_success', 'last_failure']
    search_fields = ['model_name']
    readonly_fields = [
        'total_requests', 'successful_requests', 'failed_requests',
        'avg_response_time', 'total_response_time', 'last_success', 
        'last_failure', 'reliability_score'
    ]
    ordering = ['-reliability_score', '-successful_requests']
    
    def success_rate(self, obj):
        try:
            rate = float(obj.success_rate)
            color = 'green' if rate >= 80 else 'orange' if rate >= 60 else 'red'
            return mark_safe(f'<span style="color: {color}; font-weight: bold;">{rate:.1f}%</span>')
        except (ValueError, TypeError):
            return mark_safe('<span style="color: red;">N/A</span>')
    success_rate.short_description = 'Success Rate'
    
    def reliability_score(self, obj):
        try:
            score = float(obj.reliability_score)
            color = 'green' if score >= 0.8 else 'orange' if score >= 0.6 else 'red'
            return mark_safe(f'<span style="color: {color}; font-weight: bold;">{score:.3f}</span>')
        except (ValueError, TypeError):
            return mark_safe('<span style="color: red;">N/A</span>')
    reliability_score.short_description = 'Reliability Score'
    
    actions = ['reset_consecutive_failures', 'activate_models', 'deactivate_models']
    
    def reset_consecutive_failures(self, request, queryset):
        updated = queryset.update(consecutive_failures=0)
        self.message_user(request, f'{updated} models had consecutive failures reset.')
    reset_consecutive_failures.short_description = 'Reset consecutive failures'
    
    def activate_models(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} models activated.')
    activate_models.short_description = 'Activate selected models'
    
    def deactivate_models(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} models deactivated.')
    deactivate_models.short_description = 'Deactivate selected models'


@admin.register(ResponseLog)
class ResponseLogAdmin(admin.ModelAdmin):
    """Admin interface for detailed response logs."""
    
    list_display = [
        'model_name', 'request_type', 'success', 'response_time', 
        'response_length', 'created_at'
    ]
    list_filter = ['model_name', 'request_type', 'success', 'created_at']
    search_fields = ['model_name', 'error_message']
    readonly_fields = [
        'model_name', 'request_type', 'success', 'response_time',
        'response_length', 'error_message', 'user_query_hash', 'created_at'
    ]
    ordering = ['-created_at']
    
    def response_time(self, obj):
        try:
            time_ms = float(obj.response_time) * 1000
            color = 'green' if time_ms < 2000 else 'orange' if time_ms < 5000 else 'red'
            return mark_safe(f'<span style="color: {color}; font-weight: bold;">{time_ms:.0f}ms</span>')
        except (ValueError, TypeError):
            return mark_safe('<span style="color: red;">N/A</span>')
    response_time.short_description = 'Response Time'
    
    def success(self, obj):
        if obj.success:
            return mark_safe('<span style="color: green;">Success</span>')
        else:
            return mark_safe('<span style="color: red;">Failed</span>')
    success.short_description = 'Status'
    
    def has_add_permission(self, request):
        return False  # Logs are created automatically
    
    def has_change_permission(self, request, obj=None):
        return False  # Logs should not be modified


@admin.register(ModelReliability)
class ModelReliabilityAdmin(admin.ModelAdmin):
    """Admin interface for model reliability configuration."""
    
    list_display = [
        'model_name', 'tier', 'priority', 'custom_temperature', 
        'max_retries', 'circuit_breaker_threshold', 'last_updated'
    ]
    list_filter = ['tier', 'last_updated']
    search_fields = ['model_name']
    ordering = ['tier', 'priority', 'model_name']
    
    fieldsets = (
        ('Basic Configuration', {
            'fields': ('model_name', 'tier', 'priority')
        }),
        ('Advanced Settings', {
            'fields': (
                'custom_temperature', 'max_retries', 'circuit_breaker_threshold'
            ),
            'classes': ('collapse',)
        }),
        ('System Information', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['promote_to_primary', 'demote_to_secondary', 'demote_to_emergency']
    
    def promote_to_primary(self, request, queryset):
        updated = queryset.update(tier='primary')
        self.message_user(request, f'{updated} models promoted to primary tier.')
    promote_to_primary.short_description = 'Promote to Primary tier'
    
    def demote_to_secondary(self, request, queryset):
        updated = queryset.update(tier='secondary')
        self.message_user(request, f'{updated} models demoted to secondary tier.')
    demote_to_secondary.short_description = 'Demote to Secondary tier'
    
    def demote_to_emergency(self, request, queryset):
        updated = queryset.update(tier='emergency')
        self.message_user(request, f'{updated} models demoted to emergency tier.')
    demote_to_emergency.short_description = 'Demote to Emergency tier'


# Customize admin site header
admin.site.site_header = 'AI Research Assistant Administration'
admin.site.site_title = 'AI Research Assistant'
admin.site.index_title = 'Model Performance Monitoring'
