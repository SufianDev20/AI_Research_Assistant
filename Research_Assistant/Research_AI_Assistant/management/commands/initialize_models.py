"""
Django management command to initialize OpenRouter model reliability data.
Run: python manage.py initialize_models
"""

from django.core.management.base import BaseCommand
from Research_AI_Assistant.models import ModelReliability
from Research_AI_Assistant.services.openrouter_service import FREE_MODELS, DEFAULT_MODEL


class Command(BaseCommand):
    help = 'Initialize OpenRouter model reliability configuration'

    def handle(self, *args, **options):
        self.stdout.write('Initializing OpenRouter model reliability configuration...')
        
        # Define initial model tiers based on general knowledge of model reliability
        # These can be adjusted based on actual performance data
        initial_config = {
            # Primary tier - Most reliable based on general performance
            "arcee-ai/trinity-large-preview:free": {
                "tier": "primary",
                "priority": 1,
                "custom_temperature": 0.3,
                "max_retries": 3,
                "circuit_breaker_threshold": 5
            },
            "meta-llama/llama-3.3-70b-instruct:free": {
                "tier": "primary", 
                "priority": 2,
                "custom_temperature": 0.3,
                "max_retries": 3,
                "circuit_breaker_threshold": 5
            },
            "openai/gpt-oss-120b:free": {
                "tier": "primary",
                "priority": 3,
                "custom_temperature": 0.3,
                "max_retries": 3,
                "circuit_breaker_threshold": 5
            },
            
            # Secondary tier - Good performance but less consistent
            "google/gemma-3-4b-it:free": {
                "tier": "secondary",
                "priority": 10,
                "custom_temperature": 0.3,
                "max_retries": 2,
                "circuit_breaker_threshold": 7
            },
            "stepfun/step-3.5-flash:free": {
                "tier": "secondary",
                "priority": 11,
                "custom_temperature": 0.3,
                "max_retries": 2,
                "circuit_breaker_threshold": 7
            },
            "z-ai/glm-4.5-air:free": {
                "tier": "secondary",
                "priority": 12,
                "custom_temperature": 0.3,
                "max_retries": 2,
                "circuit_breaker_threshold": 7
            },
            
            # Emergency tier - Last resort options
            "nvidia/nemotron-nano-9b-v2:free": {
                "tier": "emergency",
                "priority": 20,
                "custom_temperature": 0.3,
                "max_retries": 1,
                "circuit_breaker_threshold": 10
            },
            "nvidia/nemotron-3-nano-30b-a3b:free": {
                "tier": "emergency",
                "priority": 21,
                "custom_temperature": 0.3,
                "max_retries": 1,
                "circuit_breaker_threshold": 10
            },
            "qwen/qwen3-next-80b-a3b-instruct:free": {
                "tier": "emergency",
                "priority": 22,
                "custom_temperature": 0.3,
                "max_retries": 1,
                "circuit_breaker_threshold": 10
            },
            "meta-llama/llama-3.2-3b-instruct:free": {
                "tier": "emergency",
                "priority": 23,
                "custom_temperature": 0.3,
                "max_retries": 1,
                "circuit_breaker_threshold": 10
            }
        }
        
        created_count = 0
        updated_count = 0
        
        for model_name, config in initial_config.items():
            obj, created = ModelReliability.objects.update_or_create(
                model_name=model_name,
                defaults=config
            )
            
            if created:
                created_count += 1
                self.stdout.write(f'Created: {obj}')
            else:
                updated_count += 1
                self.stdout.write(f'Updated: {obj}')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\nModel reliability configuration initialized!\n'
                f'Created: {created_count} models\n'
                f'Updated: {updated_count} models\n'
                f'Total: {created_count + updated_count} models configured'
            )
        )
        
        # Show tier summary
        self.stdout.write('\nTier Summary:')
        for tier_choice, tier_label in ModelReliability.TIER_CHOICES:
            count = ModelReliability.objects.filter(tier=tier_choice).count()
            self.stdout.write(f'  {tier_label}: {count} models')
