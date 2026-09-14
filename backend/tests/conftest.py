"""Shared pytest fixtures: temp DB per test + TestClient wired to it."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base, get_db
from app.main import create_app
from app.services.users import get_or_create_single_user


@pytest.fixture()
def db_session(tmp_path) -> Session:
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = factory()
    get_or_create_single_user(session, 1)
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> TestClient:
    app = create_app()

    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    return TestClient(app)
