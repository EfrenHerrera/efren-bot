from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker

from efren_bot.config import Settings


def make_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_timeout=3,
        connect_args={
            "connect_timeout": 3,
            "options": "-c timezone=UTC -c statement_timeout=10000 -c lock_timeout=5000",
        },
    )


def session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)
