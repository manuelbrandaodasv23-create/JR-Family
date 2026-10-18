import os
import tempfile
import pytest
fd, path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = "sqlite:///"+path
os.environ["ENVIRONMENT"] = "test"
os.environ["FIREBASE_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-at-least-32-bytes-long"
from app.db import Base, engine
from app import models
@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield

def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    os.unlink(path)
