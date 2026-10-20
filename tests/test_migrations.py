"""The checked-in migrations must build exactly the schema the models describe."""
from pathlib import Path

import sqlalchemy as sa
from flask_migrate import upgrade

from app import create_app
from app.extensions import db

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"


def test_migrations_match_models(tmp_path):
    app = create_app("testing", {"SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'migrated.db'}"})
    with app.app_context():
        upgrade(directory=str(MIGRATIONS))
        inspector = sa.inspect(db.engine)
        for table in db.metadata.tables.values():
            actual_columns = {c["name"] for c in inspector.get_columns(table.name)}
            assert actual_columns == set(table.columns.keys()), table.name
            actual_indexes = {i["name"] for i in inspector.get_indexes(table.name)}
            assert {i.name for i in table.indexes} <= actual_indexes, table.name
