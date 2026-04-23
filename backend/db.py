from sqlmodel import Session, SQLModel, create_engine, select

from backend.config import config
from backend.models import Settings

if config.database_url:
    engine = create_engine(config.database_url, echo=False)
else:
    engine = create_engine(f"sqlite:///{config.db_path}", echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        existing = s.exec(select(Settings).where(Settings.id == 1)).first()
        if not existing:
            s.add(Settings(id=1))
            s.commit()


def get_session() -> Session:
    return Session(engine)
