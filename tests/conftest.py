"""Shared test harness: one fake DB instance + app client for all test files."""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "postgresql://fake:fake@localhost:5432/fake"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

import db  # noqa: E402
from tests.fake_db import FakeDb, seed_default_store  # noqa: E402

fake_db = FakeDb()


def fake_conn():
    return fake_db.connect()


db.get_conn = fake_conn
import api.auth_pg  # noqa: E402
import api.bookings  # noqa: E402
import api.content  # noqa: E402
api.auth_pg.get_conn = fake_conn
api.bookings.get_conn = fake_conn
api.content.get_conn = fake_conn

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


@pytest.fixture(autouse=True)
def reset_store():
    fake_db.reset()
    seed_default_store(fake_db)
    yield
    fake_db.reset()
