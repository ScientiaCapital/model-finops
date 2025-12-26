"""
Budget Alerting Service

Monitors user spending and sends notifications when budget thresholds are crossed.
Supports multiple notification channels: email (SendGrid), Slack, Discord, custom webhooks.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

import httpx

from app.database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


class AlertChannel(Enum):
    EMAIL = "email"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    LOG = "log"


@dataclass
class BudgetConfig:
    user_id: str
    monthly_budget: float
    alert_thresholds: List[float]
    alert_email: Optional[str] = None
    alert_webhook_url: Optional[str] = None
    slack_webhook_url: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    alert_cooldown_minutes: int = 60
    enabled: bool = True


@dataclass
class BudgetStatus:
    user_id: str
    current_spend: float
    monthly_budget: float
    percentage_used: float
    remaining: float
    days_in_month: int
    days_remaining: int
    daily_average: float
    projected_monthly: float
    threshold_alerts: List[Dict[str, Any]]


class BudgetAlertingService:
    """Service for monitoring budgets and sending threshold alerts."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def get_budget_config(self, user_id: str) -> Optional[BudgetConfig]:
        """Get user's budget configuration."""
        db = get_supabase_client()

        response = db.client.table("budget_configurations") \
            .select("*") \
            .eq("user_id", user_id) \
            .single() \
            .execute()

        if not response.data:
            return None

        data = response.data
        return BudgetConfig(
            user_id=data["user_id"],
            monthly_budget=data["monthly_budget"],
            alert_thresholds=data["alert_thresholds"],
            alert_email=data.get("alert_email"),
            alert_webhook_url=data.get("alert_webhook_url"),
            slack_webhook_url=data.get("slack_webhook_url"),
            discord_webhook_url=data.get("discord_webhook_url"),
            alert_cooldown_minutes=data.get("alert_cooldown_minutes", 60),
            enabled=data.get("enabled", True),
        )

    async def set_budget_config(
        self,
        user_id: str,
        monthly_budget: float,
        alert_thresholds: Optional[List[float]] = None,
        alert_email: Optional[str] = None,
        alert_webhook_url: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        alert_cooldown_minutes: int = 60,
    ) -> BudgetConfig:
        """Create or update user's budget configuration."""
        db = get_supabase_client()

        data = {
            "user_id": user_id,
            "monthly_budget": monthly_budget,
            "alert_thresholds": alert_thresholds or [0.5, 0.8, 0.9],
            "alert_email": alert_email,
            "alert_webhook_url": alert_webhook_url,
            "slack_webhook_url": slack_webhook_url,
            "discord_webhook_url": discord_webhook_url,
            "alert_cooldown_minutes": alert_cooldown_minutes,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        response = db.client.table("budget_configurations") \
            .upsert(data, on_conflict="user_id") \
            .execute()

        return BudgetConfig(**{k: v for k, v in data.items() if k != "updated_at"}, enabled=True)

    async def get_monthly_spend(self, user_id: str) -> float:
        """Get user's total spend for current month."""
        db = get_supabase_client()

        response = db.client.rpc("get_monthly_spend", {"p_user_id": user_id}).execute()

        return response.data or 0.0

    async def get_budget_status(self, user_id: str) -> Optional[BudgetStatus]:
        """Get comprehensive budget status for a user."""
        config = await self.get_budget_config(user_id)
        if not config:
            return None

        current_spend = await self.get_monthly_spend(user_id)
        now = datetime.now(timezone.utc)

        # Calculate days
        days_in_month = (now.replace(month=now.month % 12 + 1, day=1) - now.replace(day=1)).days
        day_of_month = now.day
        days_remaining = days_in_month - day_of_month + 1

        # Calculate projections
        daily_average = current_spend / day_of_month if day_of_month > 0 else 0
        projected_monthly = daily_average * days_in_month

        percentage_used = (current_spend / config.monthly_budget * 100) if config.monthly_budget > 0 else 0

        # Check which thresholds have been crossed
        threshold_alerts = []
        for threshold in sorted(config.alert_thresholds):
            threshold_pct = threshold * 100
            if percentage_used >= threshold_pct:
                threshold_alerts.append({
                    "threshold": threshold,
                    "threshold_percentage": threshold_pct,
                    "status": "exceeded",
                })

        return BudgetStatus(
            user_id=user_id,
            current_spend=current_spend,
            monthly_budget=config.monthly_budget,
            percentage_used=round(percentage_used, 2),
            remaining=max(0, config.monthly_budget - current_spend),
            days_in_month=days_in_month,
            days_remaining=days_remaining,
            daily_average=round(daily_average, 4),
            projected_monthly=round(projected_monthly, 2),
            threshold_alerts=threshold_alerts,
        )

    async def should_send_alert(
        self,
        user_id: str,
        threshold: float,
        cooldown_minutes: int = 60
    ) -> bool:
        """Check if alert should be sent (respects cooldown period)."""
        db = get_supabase_client()

        response = db.client.rpc("should_send_alert", {
            "p_user_id": user_id,
            "p_threshold": threshold,
            "p_cooldown_minutes": cooldown_minutes,
        }).execute()

        return response.data if response.data is not None else True

    async def check_and_send_alerts(self, user_id: str, current_cost: float) -> List[str]:
        """Check budget thresholds and send alerts if needed."""
        config = await self.get_budget_config(user_id)
        if not config or not config.enabled:
            return []

        if config.monthly_budget <= 0:
            return []

        percentage = current_cost / config.monthly_budget
        alerts_sent = []

        for threshold in sorted(config.alert_thresholds):
            if percentage >= threshold:
                should_send = await self.should_send_alert(
                    user_id, threshold, config.alert_cooldown_minutes
                )

                if should_send:
                    channels = await self._send_alert(config, threshold, current_cost)
                    await self._record_alert(user_id, threshold, current_cost, config.monthly_budget, channels)
                    alerts_sent.extend(channels)

        return alerts_sent

    async def _send_alert(
        self,
        config: BudgetConfig,
        threshold: float,
        current_spend: float
    ) -> List[str]:
        """Send alert through all configured channels."""
        channels_sent = []
        percentage = round(threshold * 100)
        remaining = config.monthly_budget - current_spend

        message = (
            f"🚨 Budget Alert: You've reached {percentage}% of your monthly budget!\n"
            f"Current spend: ${current_spend:.2f} / ${config.monthly_budget:.2f}\n"
            f"Remaining: ${remaining:.2f}"
        )

        # Always log
        logger.warning(f"Budget alert for user {config.user_id}: {message}")
        channels_sent.append("log")

        # Slack
        if config.slack_webhook_url:
            try:
                await self._send_slack_alert(config.slack_webhook_url, config, threshold, current_spend)
                channels_sent.append("slack")
            except Exception as e:
                logger.error(f"Failed to send Slack alert: {e}")

        # Discord
        if config.discord_webhook_url:
            try:
                await self._send_discord_alert(config.discord_webhook_url, config, threshold, current_spend)
                channels_sent.append("discord")
            except Exception as e:
                logger.error(f"Failed to send Discord alert: {e}")

        # Custom webhook
        if config.alert_webhook_url:
            try:
                await self._send_webhook_alert(config.alert_webhook_url, config, threshold, current_spend)
                channels_sent.append("webhook")
            except Exception as e:
                logger.error(f"Failed to send webhook alert: {e}")

        return channels_sent

    async def _send_slack_alert(
        self,
        webhook_url: str,
        config: BudgetConfig,
        threshold: float,
        current_spend: float
    ):
        """Send formatted Slack alert."""
        percentage = round(threshold * 100)
        remaining = config.monthly_budget - current_spend

        # Color based on severity
        color = "#36a64f" if threshold < 0.8 else "#ff9800" if threshold < 0.9 else "#f44336"

        payload = {
            "attachments": [{
                "color": color,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"🚨 Budget Alert: {percentage}% Reached",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Current Spend:*\n${current_spend:.2f}"},
                            {"type": "mrkdwn", "text": f"*Monthly Budget:*\n${config.monthly_budget:.2f}"},
                            {"type": "mrkdwn", "text": f"*Remaining:*\n${remaining:.2f}"},
                            {"type": "mrkdwn", "text": f"*Usage:*\n{percentage}%"},
                        ]
                    },
                    {
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": f"AI Cost Optimizer • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"}
                        ]
                    }
                ]
            }]
        }

        await self.http_client.post(webhook_url, json=payload)

    async def _send_discord_alert(
        self,
        webhook_url: str,
        config: BudgetConfig,
        threshold: float,
        current_spend: float
    ):
        """Send formatted Discord alert."""
        percentage = round(threshold * 100)
        remaining = config.monthly_budget - current_spend

        # Color based on severity (Discord uses decimal colors)
        color = 3066993 if threshold < 0.8 else 16750848 if threshold < 0.9 else 15158332

        payload = {
            "embeds": [{
                "title": f"🚨 Budget Alert: {percentage}% Reached",
                "color": color,
                "fields": [
                    {"name": "Current Spend", "value": f"${current_spend:.2f}", "inline": True},
                    {"name": "Monthly Budget", "value": f"${config.monthly_budget:.2f}", "inline": True},
                    {"name": "Remaining", "value": f"${remaining:.2f}", "inline": True},
                ],
                "footer": {
                    "text": f"AI Cost Optimizer • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
                }
            }]
        }

        await self.http_client.post(webhook_url, json=payload)

    async def _send_webhook_alert(
        self,
        webhook_url: str,
        config: BudgetConfig,
        threshold: float,
        current_spend: float
    ):
        """Send generic webhook alert (JSON payload)."""
        payload = {
            "event": "budget_threshold_reached",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": config.user_id,
            "threshold_percentage": threshold * 100,
            "current_spend": current_spend,
            "monthly_budget": config.monthly_budget,
            "remaining_budget": config.monthly_budget - current_spend,
            "usage_percentage": round((current_spend / config.monthly_budget) * 100, 2),
        }

        await self.http_client.post(webhook_url, json=payload)

    async def _record_alert(
        self,
        user_id: str,
        threshold: float,
        current_spend: float,
        monthly_budget: float,
        channels: List[str]
    ):
        """Record alert in database for audit trail."""
        db = get_supabase_client()

        db.client.table("budget_alerts_sent").insert({
            "user_id": user_id,
            "threshold_percentage": threshold,
            "current_spend": current_spend,
            "monthly_budget": monthly_budget,
            "alert_channels": channels,
            "status": "sent",
        }).execute()

    async def get_alert_history(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get user's alert history."""
        db = get_supabase_client()

        response = db.client.table("budget_alerts_sent") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("sent_at", desc=True) \
            .limit(limit) \
            .execute()

        return response.data or []

    async def close(self):
        """Cleanup resources."""
        await self.http_client.aclose()


# Singleton instance
_budget_service: Optional[BudgetAlertingService] = None


def get_budget_service() -> BudgetAlertingService:
    """Get or create budget alerting service instance."""
    global _budget_service
    if _budget_service is None:
        _budget_service = BudgetAlertingService()
    return _budget_service
