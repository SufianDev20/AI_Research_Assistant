from rest_framework import serializers
from .models import ModelPerformance, QueryLog, ModelReliability, ResponseLog


class QueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryLog
        fields = ["query_text", "ranking_mode", "result_count", "created_at"]


class ModelPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelPerformance
        fields = ["__all__"]


class ResponseLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResponseLog
        fields = [
            "model_name",
            "response_time",
            "success",
            "created_at",
            "error_message",
            "user_query_hash",
            "request_type",
            "response_length",
        ]


class ModelReliabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelReliability
        fields = [
            "model_name",
            "tier",
            "priority",
            "max_retries",
            "custom_temperature",
            "circuit_breaker_threshold",
            "last_updated",
        ]


class QARequestSerializer(serializers.Serializer):
    """
    Validate an incoming Multi-Paper Q&A request.

    Not a ModelSerializer: this request has no matching model, it is a
    pass-through validation shape for views.multi_paper_qa's payload.
    """

    paper_ids = serializers.ListField(
        child=serializers.CharField(min_length=1),
        min_length=1,
        max_length=10,
        help_text="OpenAlex work IDs of the selected papers (1-10).",
    )
    question = serializers.CharField(
        min_length=1, max_length=2000, trim_whitespace=True
    )
    pdf_urls = serializers.DictField(
        child=serializers.CharField(allow_blank=False),
        help_text="Mapping of paper_id -> direct PDF URL for each selected paper.",
    )

    def validate(self, attrs):
        """Ensure every paper_id has a matching pdf_url entry."""
        missing = [
            paper_id
            for paper_id in attrs["paper_ids"]
            if paper_id not in attrs["pdf_urls"]
        ]
        if missing:
            raise serializers.ValidationError(
                {"pdf_urls": f"Missing pdf_url for paper_id(s): {missing}"}
            )
        return attrs
