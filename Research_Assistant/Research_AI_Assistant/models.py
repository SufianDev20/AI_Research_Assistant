"""
Models for Research AI Assistant.
Django models reference: https://docs.djangoproject.com/en/6.0/topics/db/models/
"""

from django.db import models
from django.core.exceptions import ValidationError


class QueryLog(models.Model):
    """
    Logs each search query for analytics.
    No user PII stored — query text, mode, result count, timestamp only.
    """

    RANKING_CHOICES = [
        ("relevance", "Relevance"),
        ("open_access", "Open Access Only"),
        ("best_match", "Best Match"),
    ]

    query_text = models.CharField(max_length=500)
    ranking_mode = models.CharField(
        max_length=20,
        choices=RANKING_CHOICES,
        default="relevance",
    )
    result_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["ranking_mode"]),
        ]

    def __str__(self):
        return f"[{self.ranking_mode}] '{self.query_text[:50]}' -> {self.result_count} results"


class ModelPerformance(models.Model):
    """
    Tracks performance metrics for OpenRouter models.
    Used to identify consistent and reliable free-tier models.
    """

    model_name = models.CharField(max_length=100, unique=True, db_index=True)
    total_requests = models.PositiveIntegerField(default=0)
    successful_requests = models.PositiveIntegerField(default=0)
    failed_requests = models.PositiveIntegerField(default=0)
    avg_response_time = models.FloatField(default=0.0)  # in seconds
    total_response_time = models.FloatField(default=0.0)  # cumulative for averaging
    last_success = models.DateTimeField(null=True, blank=True)
    last_failure = models.DateTimeField(null=True, blank=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    reliability_score = models.FloatField(default=0.0)  # 0.0 to 1.0
    format_compliance_score = models.FloatField(default=0.0)  # 0.0 to 1.0
    format_compliance_count = models.PositiveIntegerField(
        default=0
    )  # total format checks
    format_compliance_passed = models.PositiveIntegerField(
        default=0
    )  # passed format checks

    class Meta:
        ordering = ["-reliability_score", "-successful_requests"]
        indexes = [
            models.Index(fields=["model_name"]),
            models.Index(fields=["reliability_score"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["last_success"]),
        ]

    def __str__(self):
        return f"{self.model_name} (Score: {self.reliability_score:.2f}, Success: {self.success_rate:.1f}%)"

    @property
    def success_rate(self):
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    def update_format_compliance(self, passed: bool):
        """Update format compliance metrics."""
        self.format_compliance_count += 1
        if passed:
            self.format_compliance_passed += 1

        # Calculate format compliance score as percentage
        if self.format_compliance_count > 0:
            self.format_compliance_score = (
                self.format_compliance_passed / self.format_compliance_count
            )
        else:
            self.format_compliance_score = 0.0

    def update_reliability_score(self):
        """Update reliability score based on multiple factors."""
        if self.total_requests == 0:
            self.reliability_score = 0.0
            return

        # Base score from success rate (40% weight - reduced from 60%)
        success_score = self.success_rate / 100.0 * 0.4

        # Response time score (10% weight - reduced from 20%) - faster is better, capped at 10 seconds
        time_score = max(0, (10 - min(self.avg_response_time, 10)) / 10) * 0.1

        # Format compliance score (30% weight) - new factor
        format_score = self.format_compliance_score * 0.3

        # Recent activity score (10% weight) - recent success is better
        recent_score = 0.0
        if self.last_success:
            from django.utils import timezone
            import datetime

            days_since_success = (timezone.now() - self.last_success).days
            recent_score = max(0, (7 - min(days_since_success, 7)) / 7) * 0.1

        # Consecutive failures penalty (10% weight)
        failure_penalty = max(0, 1 - (self.consecutive_failures / 10)) * 0.1

        self.reliability_score = (
            success_score + time_score + format_score + recent_score + failure_penalty
        )
        self.reliability_score = max(
            0.0, min(1.0, self.reliability_score)
        )  # Clamp between 0 and 1


class ResponseLog(models.Model):
    """
    Detailed logging of individual LLM responses for quality analysis.
    """

    model_name = models.CharField(max_length=100, db_index=True)
    request_type = models.CharField(
        max_length=20,
        choices=[
            ("summary", "Paper Summary"),
            ("title", "Title Generation"),
            ("other", "Other"),
        ],
    )
    success = models.BooleanField()
    response_time = models.FloatField()  # in seconds
    response_length = models.PositiveIntegerField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    user_query_hash = models.CharField(
        max_length=64, null=True, blank=True
    )  # for consistency analysis
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["model_name", "created_at"]),
            models.Index(fields=["success"]),
            models.Index(fields=["request_type"]),
            models.Index(fields=["user_query_hash"]),
        ]

    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.model_name} - {self.request_type} ({self.response_time:.2f}s)"


class ModelReliability(models.Model):
    """
    Dynamic model reliability ranking with configurable tiers.
    """

    TIER_CHOICES = [
        ("primary", "Primary - Most Reliable"),
        ("secondary", "Secondary - Good Performance"),
        ("emergency", "Emergency - Last Resort"),
        ("disabled", "Disabled - Not Available"),
    ]

    model_name = models.CharField(max_length=100, unique=True, db_index=True)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default="secondary")
    priority = models.PositiveIntegerField(default=50)  # Lower number = higher priority
    custom_temperature = models.FloatField(null=True, blank=True)
    max_retries = models.PositiveIntegerField(default=3)
    circuit_breaker_threshold = models.PositiveIntegerField(
        default=5
    )  # consecutive failures before disabling
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tier", "priority", "model_name"]
        indexes = [
            models.Index(fields=["tier", "priority"]),
            models.Index(fields=["model_name"]),
        ]

    def __str__(self):
        return f"{self.model_name} ({self.get_tier_display()})"

    def clean(self):
        """Validate model configuration."""
        if self.custom_temperature is not None and not (
            0.0 <= self.custom_temperature <= 2.0
        ):
            raise ValidationError("Custom temperature must be between 0.0 and 2.0")
        if self.priority < 0:
            raise ValidationError("Priority cannot be negative")
