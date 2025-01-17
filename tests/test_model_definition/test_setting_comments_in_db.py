import databases
import pytest
import sqlalchemy

import ormar
from ormar.models import Model
from tests.settings import DATABASE_URL

metadata = sqlalchemy.MetaData()

database = databases.Database(DATABASE_URL, force_rollback=True)


class Comment(Model):
    class Meta(ormar.ModelMeta):
        tablename = "comments"
        metadata = metadata
        database = database

    test: int = ormar.Integer(primary_key=True, comment="primary key of comments")
    test_string: str = ormar.String(max_length=250, comment="test that it works")


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_comments_are_set_in_db():
    columns = Comment.Meta.table.c
    for c in columns:
        assert c.comment == Comment.Meta.model_fields[c.name].comment
