"""
Models for Research AI Assistant.
Django models reference: https://docs.djangoproject.com/en/6.0/topics/db/models/
"""

from django.db import models


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
