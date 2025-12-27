"""Admin service for feedback and learning analytics using Supabase."""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

from app.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class AsyncAdminService:
    """
    Async admin service for feedback summary and learning analytics.

    Uses Supabase client for all database operations.
    """

    def __init__(self, scheduler=None):
        """Initialize admin service with Supabase client.

        Args:
            scheduler: Optional RetrainingScheduler instance for getting next run info
        """
        self.supabase = get_supabase_client()
        self.scheduler = scheduler

    async def get_feedback_summary(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get feedback statistics summary.

        Args:
            user_id: Optional user ID for filtering (admin sees all if None)

        Returns:
            Dictionary with:
            - total_feedback: Total count of feedback
            - avg_quality_score: Average quality score
            - models: Per-model statistics
        """
        try:
            # Use admin client if no user_id (see all feedback)
            # Otherwise use regular client with RLS filtering
            client = self.supabase.admin_client if (user_id is None and self.supabase.admin_client) else self.supabase.client

            # Build query with optional user filter
            query = client.table('routing_feedback').select('*')
            if user_id:
                query = query.eq('user_id', user_id)

            # Execute query
            result = query.execute()
            feedback_data = result.data if result.data else []

            # Calculate aggregate stats
            total_feedback = len(feedback_data)

            if total_feedback == 0:
                return {
                    'total_feedback': 0,
                    'avg_quality_score': 0.0,
                    'models': []
                }

            # Calculate avg quality score
            quality_scores = [f.get('quality_score', 0) for f in feedback_data if f.get('quality_score') is not None]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

            # Calculate per-model stats
            model_stats = {}
            for feedback in feedback_data:
                model = feedback.get('selected_model')
                if not model:
                    continue

                if model not in model_stats:
                    model_stats[model] = {
                        'selected_model': model,
                        'count': 0,
                        'quality_scores': [],
                        'correct_count': 0,
                        'total_with_correctness': 0
                    }

                stats = model_stats[model]
                stats['count'] += 1

                if feedback.get('quality_score') is not None:
                    stats['quality_scores'].append(feedback['quality_score'])

                if feedback.get('is_correct') is not None:
                    stats['total_with_correctness'] += 1
                    if feedback['is_correct']:
                        stats['correct_count'] += 1

            # Format model stats
            models = []
            for model, stats in model_stats.items():
                models.append({
                    'selected_model': model,
                    'count': stats['count'],
                    'avg_quality': sum(stats['quality_scores']) / len(stats['quality_scores']) if stats['quality_scores'] else 0.0,
                    'correctness_rate': stats['correct_count'] / stats['total_with_correctness'] if stats['total_with_correctness'] > 0 else 0.0
                })

            # Sort by count descending
            models.sort(key=lambda x: x['count'], reverse=True)

            return {
                'total_feedback': total_feedback,
                'avg_quality_score': avg_quality,
                'models': models
            }

        except Exception as e:
            logger.error(f"Error fetching feedback summary: {e}")
            # Return empty stats on error
            return {
                'total_feedback': 0,
                'avg_quality_score': 0.0,
                'models': []
            }

    async def get_learning_status(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get learning pipeline status.

        Args:
            user_id: Optional user ID (not used - learning is global)

        Returns:
            Dictionary with:
            - last_retraining_run: ISO timestamp of last run
            - next_scheduled_run: ISO timestamp of next scheduled run (TBD)
            - confidence_distribution: Counts by confidence level
            - total_patterns: Total unique patterns
        """
        try:
            # Use admin client if no user_id (learning is global)
            client = self.supabase.admin_client if (user_id is None and self.supabase.admin_client) else self.supabase.client

            # Get all performance history records
            result = client.table('model_performance_history') \
                .select('retraining_run_id, updated_at, confidence_level, pattern') \
                .order('updated_at', desc=True) \
                .execute()

            history_data = result.data if result.data else []

            if not history_data:
                return {
                    'last_retraining_run': None,
                    'next_scheduled_run': None,
                    'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
                    'total_patterns': 0
                }

            # Get the most recent retraining run ID
            latest_run_id = history_data[0]['retraining_run_id']
            last_run_timestamp = history_data[0]['updated_at']

            # Filter records from latest run
            latest_run_data = [r for r in history_data if r['retraining_run_id'] == latest_run_id]

            # Calculate confidence distribution (count unique patterns per confidence level)
            conf_dist = {'high': 0, 'medium': 0, 'low': 0}
            patterns_by_conf = {'high': set(), 'medium': set(), 'low': set()}

            for record in latest_run_data:
                conf_level = record.get('confidence_level', 'low')
                pattern = record.get('pattern')
                if pattern and conf_level in patterns_by_conf:
                    patterns_by_conf[conf_level].add(pattern)

            for conf_level, patterns in patterns_by_conf.items():
                conf_dist[conf_level] = len(patterns)

            total_patterns = sum(conf_dist.values())

            # Get next scheduled run time from scheduler if available
            next_run = None
            if self.scheduler and self.scheduler.is_running():
                jobs = self.scheduler.get_jobs()
                if jobs and len(jobs) > 0:
                    next_run_time = jobs[0].next_run_time
                    if next_run_time:
                        next_run = next_run_time.isoformat()

            return {
                'last_retraining_run': last_run_timestamp,  # Already ISO format from Supabase
                'next_scheduled_run': next_run,
                'confidence_distribution': conf_dist,
                'total_patterns': total_patterns
            }

        except Exception as e:
            logger.error(f"Error fetching learning status: {e}")
            return {
                'last_retraining_run': None,
                'next_scheduled_run': None,
                'confidence_distribution': {'high': 0, 'medium': 0, 'low': 0},
                'total_patterns': 0
            }

    async def get_performance_trends(self, pattern: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get performance trends for a specific pattern.

        Args:
            pattern: Pattern to analyze (e.g., 'code', 'explanation')
            user_id: Optional user ID (not used - trends are global)

        Returns:
            List of trend records with model performance over time
        """
        try:
            # Use admin client if no user_id (trends are global)
            client = self.supabase.admin_client if (user_id is None and self.supabase.admin_client) else self.supabase.client

            result = client.table('model_performance_history') \
                .select('model, avg_quality_score, correctness_rate, sample_count, confidence_level, updated_at') \
                .eq('pattern', pattern) \
                .order('updated_at', desc=True) \
                .limit(20) \
                .execute()

            trends = result.data if result.data else []

            return trends

        except Exception as e:
            logger.error(f"Error fetching performance trends for pattern '{pattern}': {e}")
            return []

    async def aggregate_feedback_for_learning(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Aggregate routing feedback for learning/retraining.

        Queries routing_feedback table and aggregates stats by pattern and model.
        Used by FeedbackTrainer for retraining the routing engine.

        Returns:
            Nested dict: {pattern: {model: {stats}}}
        """
        try:
            # Query routing feedback from last 90 days with minimum sample threshold
            # Use raw SQL via Supabase RPC function for complex aggregation
            result = self.supabase.client.table('routing_feedback') \
                .select('prompt_pattern, selected_model, quality_score, is_correct, complexity_score') \
                .not_.is_('prompt_pattern', 'null') \
                .not_.is_('selected_model', 'null') \
                .execute()

            feedback_data = result.data if result.data else []

            # Aggregate by pattern and model
            aggregates = {}
            pattern_model_data = {}

            for row in feedback_data:
                pattern = row['prompt_pattern']
                model = row['selected_model']

                key = (pattern, model)
                if key not in pattern_model_data:
                    pattern_model_data[key] = {
                        'quality_scores': [],
                        'correct_count': 0,
                        'total_with_correctness': 0,
                        'complexity_scores': []
                    }

                data = pattern_model_data[key]

                if row.get('quality_score') is not None:
                    data['quality_scores'].append(float(row['quality_score']))

                if row.get('is_correct') is not None:
                    data['total_with_correctness'] += 1
                    if row['is_correct']:
                        data['correct_count'] += 1

                if row.get('complexity_score') is not None:
                    data['complexity_scores'].append(float(row['complexity_score']))

            # Calculate stats and filter by minimum sample size
            result_dict = {}
            for (pattern, model), data in pattern_model_data.items():
                sample_count = len(data['quality_scores'])

                # Require at least 3 samples
                if sample_count < 3:
                    continue

                avg_quality = sum(data['quality_scores']) / len(data['quality_scores']) if data['quality_scores'] else 0.0
                correctness_rate = data['correct_count'] / data['total_with_correctness'] if data['total_with_correctness'] > 0 else 0.0
                avg_complexity = sum(data['complexity_scores']) / len(data['complexity_scores']) if data['complexity_scores'] else 0.0

                if pattern not in result_dict:
                    result_dict[pattern] = {}

                result_dict[pattern][model] = {
                    'sample_count': sample_count,
                    'avg_quality': avg_quality,
                    'correctness': correctness_rate,
                    'avg_complexity': avg_complexity
                }

            return result_dict

        except Exception as e:
            logger.error(f"Error aggregating feedback for learning: {e}")
            return {}

    async def store_performance_history(
        self,
        pattern: str,
        model: str,
        stats: Dict[str, Any],
        confidence: str,
        run_id: str
    ) -> None:
        """
        Store model performance history after retraining.

        Args:
            pattern: Prompt pattern
            model: Model name (e.g., "gemini/gemini-1.5-flash")
            stats: Performance statistics dict with keys:
                - avg_quality: Average quality score
                - correctness: Correctness rate
                - count: Sample count
            confidence: Confidence level ('high', 'medium', 'low')
            run_id: Retraining run ID
        """
        try:
            # Extract provider from model name
            provider = model.split('/')[0] if '/' in model else 'unknown'

            data = {
                'pattern': pattern,
                'model': model,
                'avg_quality_score': float(stats.get('avg_quality', 0)),
                'correctness_rate': float(stats.get('correctness', 0)),
                'sample_count': int(stats.get('count', 0)),
                'confidence_level': confidence,
                'retraining_run_id': run_id,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }

            # Use admin client to bypass RLS (learning is global)
            await self.supabase.insert(
                table='model_performance_history',
                data=data,
                use_admin=True
            )

            logger.debug(f"Stored performance history: {pattern}/{model} (confidence={confidence})")

        except Exception as e:
            logger.error(f"Error storing performance history for {pattern}/{model}: {e}")

    async def store_routing_feedback(
        self,
        request_id: str,
        quality_score: float,
        is_correct: bool,
        is_helpful: Optional[bool] = None,
        comment: Optional[str] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> int:
        """
        Store routing feedback from production usage.

        Args:
            request_id: Request ID from routing decision
            quality_score: Quality rating (0.0-1.0)
            is_correct: Was the routing decision correct
            is_helpful: Was the response helpful
            comment: Optional user comment
            user_id: Optional user identifier
            session_id: Optional session identifier

        Returns:
            Feedback ID (primary key)
        """
        try:
            # First, get context from routing_metrics
            metrics_result = self.supabase.client.table('routing_metrics') \
                .select('provider, model, metadata') \
                .eq('request_id', request_id) \
                .limit(1) \
                .execute()

            # Extract context if available
            if metrics_result.data and len(metrics_result.data) > 0:
                metrics = metrics_result.data[0]
                provider = metrics.get('provider', 'unknown')
                model = metrics.get('model', 'unknown')
                metadata = metrics.get('metadata', {})
                pattern = metadata.get('pattern', 'unknown') if metadata else 'unknown'
                complexity = metadata.get('complexity') if metadata else None
            else:
                # No metrics found (likely cache hit) - use defaults
                logger.warning(f"No routing_metrics found for request_id={request_id} (likely cache hit)")
                provider = 'cache'
                model = 'unknown'
                pattern = 'unknown'
                complexity = None

            # Normalize quality_score to 0-1 range if needed (handle 1-5 scale)
            normalized_quality = float(quality_score)
            if normalized_quality > 1.0:
                normalized_quality = normalized_quality / 5.0  # Convert 1-5 to 0.2-1.0

            # Insert feedback
            feedback_data = {
                'request_id': request_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'quality_score': normalized_quality,
                'is_correct': bool(is_correct),
                'is_helpful': bool(is_helpful) if is_helpful is not None else None,
                'prompt_pattern': pattern,
                'selected_provider': provider,
                'selected_model': model,
                'user_id': user_id,
                'session_id': session_id,
                'comment': comment
            }

            # Use admin client if no user_id (public feedback)
            # Otherwise use regular client to respect RLS
            use_admin = user_id is None

            result = await self.supabase.insert(
                table='routing_feedback',
                data=feedback_data,
                use_admin=use_admin
            )

            feedback_id = result.get('id')
            logger.info(f"Stored feedback {feedback_id} for request {request_id}")

            return feedback_id

        except Exception as e:
            logger.error(f"Error storing routing feedback: {e}")
            raise

    async def get_feedback_by_id(self, feedback_id: int) -> Optional[Dict[str, Any]]:
        """
        Get feedback by ID.

        Args:
            feedback_id: Feedback record ID

        Returns:
            Feedback dictionary or None if not found
        """
        try:
            result = self.supabase.client.table('routing_feedback') \
                .select('*') \
                .eq('id', feedback_id) \
                .limit(1) \
                .execute()

            if result.data and len(result.data) > 0:
                return result.data[0]
            else:
                return None

        except Exception as e:
            logger.error(f"Error retrieving feedback {feedback_id}: {e}")
            return None


# Singleton instance
_admin_service = None


def get_admin_service(scheduler=None) -> AsyncAdminService:
    """Get singleton admin service instance.

    Args:
        scheduler: Optional RetrainingScheduler instance (only used on first call)

    Returns:
        Singleton AsyncAdminService instance
    """
    global _admin_service
    if _admin_service is None:
        _admin_service = AsyncAdminService(scheduler=scheduler)
    return _admin_service
