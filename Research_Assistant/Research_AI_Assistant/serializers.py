from rest_framework import serializers
from .models import ModelPerformance, QueryLog, ModelReliability, ResponseLog
from .services.extract_service import MAX_PDF_CANDIDATES

MAX_PDF_URL_LENGTH = 500


class QueryLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueryLog
        fields = ["query_text", "ranking_mode", "result_count", "created_at"]


class ModelPerformanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelPerformance
        fields = "__all__"


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


class PDFUrlsValueField(serializers.Field):
    """One paper's PDF URL(s): a single URL string or a short ordered list. Always yields a list."""

    def to_internal_value(self, data):
        urls = [data] if isinstance(data, str) else data
        if not isinstance(urls, list) or not urls:
            raise serializers.ValidationError(
                "Expected a PDF URL or a non-empty list of PDF URLs."
            )
        if len(urls) > MAX_PDF_CANDIDATES:
            raise serializers.ValidationError(
                f"At most {MAX_PDF_CANDIDATES} PDF URLs per paper."
            )
        cleaned = []
        for url in urls:
            if not isinstance(url, str) or not url.strip():
                raise serializers.ValidationError("Each PDF URL must be a non-empty string.")
            if len(url.strip()) > MAX_PDF_URL_LENGTH:
                raise serializers.ValidationError(
                    f"PDF URLs must be {MAX_PDF_URL_LENGTH} characters or fewer."
                )
            cleaned.append(url.strip())
        return cleaned

    def to_representation(self, value):
        return value


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
        child=PDFUrlsValueField(),
        help_text="Mapping of paper_id -> direct PDF URL (or ordered list of up to 3 candidate URLs) for each selected paper.",
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
