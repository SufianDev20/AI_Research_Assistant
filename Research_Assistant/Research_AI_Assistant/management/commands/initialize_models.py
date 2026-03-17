"""
Django management command to initialize OpenRouter model reliability data.
Run: python manage.py initialize_models
"""

from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Q
from Research_AI_Assistant.models import ModelReliability, ModelPerformance
from Research_AI_Assistant.services.openrouter_service import FREE_MODELS, DEFAULT_MODEL


class Command(BaseCommand):
    help = 'Initialize OpenRouter model reliability configuration based on actual performance data'

    def handle(self, *args, **options):
        self.stdout.write('Initializing OpenRouter model reliability configuration...')
        
        # Get actual performance data to inform tier decisions
        performance_data = self.get_performance_metrics()
        
        # Define data-driven model tiers based on actual performance
        data_driven_config = self.generate_data_driven_config(performance_data)
        
        created_count = 0
        updated_count = 0
        
        for model_name, config in data_driven_config.items():
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
        
        # Show tier summary and performance insights
        self.show_tier_summary()
        self.show_performance_insights(performance_data)
    
    def get_performance_metrics(self):
        """Get actual performance metrics for all models."""
        metrics = {}
        
        for model_name in FREE_MODELS:
            try:
                perf = ModelPerformance.objects.filter(model_name=model_name).first()
                if perf:
                    metrics[model_name] = {
                        'total_requests': perf.total_requests,
                        'success_rate': perf.success_rate,
                        'reliability_score': perf.reliability_score,
                        'format_compliance_score': getattr(perf, 'format_compliance_score', 0.0),
                        'format_compliance_count': getattr(perf, 'format_compliance_count', 0),
                        'format_compliance_passed': getattr(perf, 'format_compliance_passed', 0),
                        'avg_response_time': perf.avg_response_time,
                        'consecutive_failures': perf.consecutive_failures,
                        'is_active': perf.is_active
                    }
                else:
                    # No data yet - use default values
                    metrics[model_name] = {
                        'total_requests': 0,
                        'success_rate': 0.0,
                        'reliability_score': 0.0,
                        'format_compliance_score': 0.0,
                        'format_compliance_count': 0,
                        'format_compliance_passed': 0,
                        'avg_response_time': 0.0,
                        'consecutive_failures': 0,
                        'is_active': True
                    }
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f'Error getting metrics for {model_name}: {e}')
                )
                metrics[model_name] = {
                    'total_requests': 0, 'success_rate': 0.0, 'reliability_score': 0.0,
                    'format_compliance_score': 0.0, 'format_compliance_count': 0, 'format_compliance_passed': 0,
                    'avg_response_time': 0.0, 'consecutive_failures': 0, 'is_active': True
                }
        
        return metrics
    
    def generate_data_driven_config(self, performance_data):
        """Generate model configuration based on actual performance data."""
        config = {}
        
        # Sort models by reliability score (descending) for tier assignment
        sorted_models = sorted(
            performance_data.items(),
            key=lambda x: (
                x[1]['reliability_score'],  # Primary: reliability score
                x[1]['format_compliance_score'],  # Secondary: format compliance
                -x[1]['avg_response_time'] if x[1]['avg_response_time'] > 0 else 0,  # Tertiary: faster is better
                x[1]['total_requests']  # Quaternary: more experience
            ),
            reverse=True
        )
        
        # Assign tiers based on performance thresholds
        total_models = len(sorted_models)
        primary_count = max(1, total_models // 3)  # Top 33%
        secondary_count = max(1, total_models // 2)  # Next 50%
        
        for i, (model_name, metrics) in enumerate(sorted_models):
            # Determine tier based on performance
            if i < primary_count and metrics['reliability_score'] >= 0.7:
                tier = "primary"
                priority = i + 1
                max_retries = 3
                circuit_breaker_threshold = 5
            elif i < secondary_count and metrics['reliability_score'] >= 0.4:
                tier = "secondary"
                priority = i + 10
                max_retries = 2
                circuit_breaker_threshold = 7
            else:
                tier = "emergency"
                priority = i + 20
                max_retries = 1
                circuit_breaker_threshold = 10
            
            # Adjust temperature based on format compliance
            if metrics['format_compliance_score'] >= 0.8:
                custom_temperature = 0.2  # Lower temp for consistent models
            elif metrics['format_compliance_score'] >= 0.5:
                custom_temperature = 0.3  # Standard temp
            else:
                custom_temperature = 0.4  # Higher temp for inconsistent models
            
            config[model_name] = {
                "tier": tier,
                "priority": priority,
                "custom_temperature": custom_temperature,
                "max_retries": max_retries,
                "circuit_breaker_threshold": circuit_breaker_threshold
            }
            
            # Log the assignment reasoning
            self.stdout.write(
                f'{model_name}: {tier.upper()} (Reliability: {metrics["reliability_score"]:.3f}, '
                f'Format: {metrics["format_compliance_score"]:.1%}, Requests: {metrics["total_requests"]})'
            )
        
        return config
    
    def show_tier_summary(self):
        """Display tier distribution summary."""
        self.stdout.write('\nTier Summary:')
        for tier_choice, tier_label in ModelReliability.TIER_CHOICES:
            count = ModelReliability.objects.filter(tier=tier_choice).count()
            self.stdout.write(f'  {tier_label}: {count} models')
    
    def show_performance_insights(self, performance_data):
        """Display performance insights based on collected data."""
        self.stdout.write('\nPerformance Insights:')
        
        # Calculate averages
        active_models = [m for m in performance_data.values() if m['is_active']]
        if active_models:
            avg_reliability = sum(m['reliability_score'] for m in active_models) / len(active_models)
            avg_format_compliance = sum(m['format_compliance_score'] for m in active_models if m['format_compliance_count'] > 0) / len([m for m in active_models if m['format_compliance_count'] > 0]) if any(m['format_compliance_count'] > 0 for m in active_models) else 0
            avg_response_time = sum(m['avg_response_time'] for m in active_models if m['avg_response_time'] > 0) / len([m for m in active_models if m['avg_response_time'] > 0]) if any(m['avg_response_time'] > 0 for m in active_models) else 0
            
            self.stdout.write(f'  Average reliability score: {avg_reliability:.3f}')
            self.stdout.write(f'  Average format compliance: {avg_format_compliance:.1%}')
            self.stdout.write(f'  Average response time: {avg_response_time:.2f}s')
        
        # Show top performers
        top_models = sorted(
            performance_data.items(),
            key=lambda x: x[1]['reliability_score'],
            reverse=True
        )[:3]
        
        self.stdout.write('\nTop 3 Models by Reliability:')
        for i, (model_name, metrics) in enumerate(top_models, 1):
            self.stdout.write(
                f'  {i}. {model_name}: {metrics["reliability_score"]:.3f} '
                f'(Format: {metrics["format_compliance_score"]:.1%}, '
                f'Requests: {metrics["total_requests"]})'
            )
        
        # Show format compliance leaders
        models_with_format_data = [(m, d) for m, d in performance_data.items() if d['format_compliance_count'] > 0]
        if models_with_format_data:
            format_leaders = sorted(
                models_with_format_data,
                key=lambda x: x[1]['format_compliance_score'],
                reverse=True
            )[:3]
            
            self.stdout.write('\nTop 3 Models by Format Compliance:')
            for i, (model_name, metrics) in enumerate(format_leaders, 1):
                self.stdout.write(
                    f'  {i}. {model_name}: {metrics["format_compliance_score"]:.1%} '
                    f'({metrics["format_compliance_passed"]}/{metrics["format_compliance_count"]} checks)'
                )
        else:
            self.stdout.write('\nTop 3 Models by Format Compliance:')
            self.stdout.write('  No format compliance data available yet - make some summary requests!')
        
        # Models needing more data
        models_needing_data = [(m, d) for m, d in performance_data.items() if d['total_requests'] < 5]
        if models_needing_data:
            self.stdout.write(f'\nModels needing more data (< 5 requests): {len(models_needing_data)}')
            for model_name, metrics in models_needing_data[:5]:  # Show first 5
                self.stdout.write(f'  - {model_name}: {metrics["total_requests"]} requests')
