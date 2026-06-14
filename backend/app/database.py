from sqlalchemy import create_engine, Engine
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase


class Base(DeclarativeBase):
    pass


def get_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
