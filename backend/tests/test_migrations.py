"""The Alembic revision graph: two branches merged from main must not leave two heads."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def test_migrations_have_a_single_head():
    heads = ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_heads()

    assert len(heads) == 1, f"several Alembic heads, point one down_revision at the other: {heads}"
