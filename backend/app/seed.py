from sqlalchemy.orm import Session

from app.models import User


def seed_default_user(session: Session, username: str) -> User:
    existing = session.query(User).filter(User.username == username).first()
    if existing:
        return existing
    user = User(username=username)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def seed_from_config(session: Session) -> User:
    from app.config import Settings
    settings = Settings()
    return seed_default_user(session, settings.default_owner_username)
