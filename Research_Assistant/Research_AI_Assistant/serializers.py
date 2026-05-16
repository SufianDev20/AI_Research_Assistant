from rest_framework import serializers
from .models import ModelPerformance, QueryLog,ModelReliability, ResponseLog
class QueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model= QueryLog
        fields=['query_text','ranking_mode','result_count','created_at']

class ModelPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model=ModelPerformance
        fields=['__all__']
class ResponseLogSerializer(serializers.ModelSerializer):
    class Meta:
        model=ResponseLog
        fields=['model_name','response_time','success','created_at','error_message','user_query_hash','request_type','response_length']
        
class ModelReliabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model=ModelReliability
        fields=['model_name','tier','priority','max_retries','custom_temperature','circuit_breaker_threshold','last_updated']