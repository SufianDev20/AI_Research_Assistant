from django.apps import AppConfig
from django.conf import settings
from pyalex import Works


class ResearchAiAssistantConfig(AppConfig):
    name = "Research_AI_Assistant"

    def ready(self):
        Works.email = settings.OPENALEX_EMAIL
