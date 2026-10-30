"""Builds the plant from settings. Defaults are mocked end to end."""

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from efren_bot.collection.models import CollectionAnnotation, CollectionMessage
from efren_bot.config import Settings
from efren_bot.factory import effects as fx
from efren_bot.factory.executor import Executor, ScraftOpsExecutor
from efren_bot.factory.intake import (
    NotionAdapter,
    NotionHttpClient,
    PullAdapter,
    SlackCollectionAdapter,
)
from efren_bot.factory.models import FactoryItem
from efren_bot.factory.profiles import ProfileRegistry
from efren_bot.factory.projects import ProjectRegistry
from efren_bot.factory.service import FactoryService
from efren_bot.factory.triage import AdmissionPolicy


def slack_flagged_query(sessions: sessionmaker):
    """Stored Slack messages a person marked as requiring attention. Reads our own DB only."""

    def query(since: datetime | None) -> list[dict]:
        stmt = (
            select(CollectionMessage, CollectionAnnotation)
            .join(
                CollectionAnnotation,
                (CollectionAnnotation.source_scope == CollectionMessage.source_scope)
                & (CollectionAnnotation.channel_id == CollectionMessage.channel_id)
                & (CollectionAnnotation.message_id == CollectionMessage.message_id),
            )
            .where(CollectionAnnotation.attention == "required")
            .order_by(CollectionMessage.occurred_at)
        )
        if since is not None:
            stmt = stmt.where(CollectionMessage.occurred_at > since)
        with sessions() as session:
            return [
                {
                    "channel_id": m.channel_id,
                    "channel_name": m.channel_name,
                    "message_id": m.message_id,
                    "thread_id": m.thread_id,
                    "actor_id": m.actor_id,
                    "text": m.text,
                    "occurred_at": m.occurred_at,
                    "source_url": m.source_url,
                    "attention": a.attention,
                    "category": a.category,
                }
                for m, a in session.execute(stmt)
            ]

    return query


def last_seen(sessions: sessionmaker, source_kind: str) -> datetime | None:
    with sessions() as session:
        return session.scalar(
            select(func.max(FactoryItem.occurred_at)).where(FactoryItem.source_kind == source_kind)
        )


def build_notion_client(settings: Settings) -> NotionHttpClient | None:
    """Real Notion only when the host supplied both a token and a database; otherwise absent."""
    if not (settings.factory_notion_token and settings.factory_notion_database_id):
        return None
    return NotionHttpClient(
        settings.factory_notion_token,
        settings.factory_notion_database_id,
        status_property=settings.factory_notion_status_property,
    )


def build_gateway(settings: Settings, notion_client=None) -> fx.EffectGateway:
    if settings.factory_gateway == "recording":
        return fx.RecordingGateway()
    routes: dict[str, fx.EffectGateway] = {"open_pr": fx.GlabGateway()}
    if notion_client is not None:
        routes["update_notion"] = fx.NotionGateway(notion_client)
    return fx.CompositeGateway(routes)


def build_executor(settings: Settings) -> Executor:
    return ScraftOpsExecutor(
        settings.factory_scraft_ops_bin,
        state_dir=settings.factory_state_dir or None,
        profile_dir=settings.factory_profiles_dir or None,
    )


def build_service(
    settings: Settings,
    sessions: sessionmaker,
    *,
    executor: Executor | None = None,
    gateway: fx.EffectGateway | None = None,
    notion_client=None,
) -> FactoryService:
    notion_client = notion_client or build_notion_client(settings)
    projects = (
        ProjectRegistry.load(settings.factory_projects_file)
        if settings.factory_projects_file
        else ProjectRegistry([])
    )
    profile_dirs = [settings.factory_profiles_dir] if settings.factory_profiles_dir else []
    return FactoryService(
        sessions,
        projects=projects,
        profiles=ProfileRegistry.load(*profile_dirs),
        policy=AdmissionPolicy.load(),
        executor=executor or build_executor(settings),
        gateway=gateway or build_gateway(settings, notion_client),
        agent_executor=settings.factory_agent_executor,
        agent_fallbacks=settings.factory_agent_fallbacks,
        effect_ttl=timedelta(hours=settings.factory_effect_ttl_hours),
    )


def pull_adapters(
    sessions: sessionmaker, *, notion_client=None, notion_status_property: str = "Status"
) -> dict:
    notion_adapter: PullAdapter | None = (
        NotionAdapter(notion_client, status_property=notion_status_property)
        if notion_client is not None
        else None
    )
    adapters: dict[str, PullAdapter] = {
        "slack": SlackCollectionAdapter(slack_flagged_query(sessions))
    }
    if notion_adapter is not None:
        adapters["notion"] = notion_adapter
    return adapters
