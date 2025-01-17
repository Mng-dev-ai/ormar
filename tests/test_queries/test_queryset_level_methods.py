from typing import Optional

import databases
import pytest
import sqlalchemy

import ormar
from ormar.exceptions import (
    ModelPersistenceError, QueryDefinitionError,
    ModelListEmptyError
)
from tests.settings import DATABASE_URL

database = databases.Database(DATABASE_URL, force_rollback=True)
metadata = sqlalchemy.MetaData()


class Book(ormar.Model):
    class Meta:
        tablename = "books"
        metadata = metadata
        database = database

    id: int = ormar.Integer(primary_key=True)
    title: str = ormar.String(max_length=200)
    author: str = ormar.String(max_length=100)
    genre: str = ormar.String(
        max_length=100,
        default="Fiction",
        choices=["Fiction", "Adventure", "Historic", "Fantasy"],
    )


class ToDo(ormar.Model):
    class Meta:
        tablename = "todos"
        metadata = metadata
        database = database

    id: int = ormar.Integer(primary_key=True)
    text: str = ormar.String(max_length=500)
    completed: bool = ormar.Boolean(default=False)


class Category(ormar.Model):
    class Meta:
        tablename = "categories"
        metadata = metadata
        database = database

    id: int = ormar.Integer(primary_key=True)
    name: str = ormar.String(max_length=500)


class Note(ormar.Model):
    class Meta:
        tablename = "notes"
        metadata = metadata
        database = database

    id: int = ormar.Integer(primary_key=True)
    text: str = ormar.String(max_length=500)
    category: Optional[Category] = ormar.ForeignKey(Category)


@pytest.fixture(autouse=True, scope="module")
def create_test_database():
    engine = sqlalchemy.create_engine(DATABASE_URL)
    metadata.drop_all(engine)
    metadata.create_all(engine)
    yield
    metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_delete_and_update():
    async with database:
        async with database.transaction(force_rollback=True):
            await Book.objects.create(
                title="Tom Sawyer", author="Twain, Mark", genre="Adventure"
            )
            await Book.objects.create(
                title="War and Peace", author="Tolstoy, Leo", genre="Fiction"
            )
            await Book.objects.create(
                title="Anna Karenina", author="Tolstoy, Leo", genre="Fiction"
            )
            await Book.objects.create(
                title="Harry Potter", author="Rowling, J.K.", genre="Fantasy"
            )
            await Book.objects.create(
                title="Lord of the Rings", author="Tolkien, J.R.", genre="Fantasy"
            )

            all_books = await Book.objects.all()
            assert len(all_books) == 5

            await Book.objects.filter(author="Tolstoy, Leo").update(
                author="Lenin, Vladimir"
            )
            all_books = await Book.objects.filter(author="Lenin, Vladimir").all()
            assert len(all_books) == 2

            historic_books = await Book.objects.filter(genre="Historic").all()
            assert len(historic_books) == 0

            with pytest.raises(QueryDefinitionError):
                await Book.objects.update(genre="Historic")

            await Book.objects.filter(author="Lenin, Vladimir").update(genre="Historic")

            historic_books = await Book.objects.filter(genre="Historic").all()
            assert len(historic_books) == 2

            await Book.objects.delete(genre="Fantasy")
            all_books = await Book.objects.all()
            assert len(all_books) == 3

            await Book.objects.update(each=True, genre="Fiction")
            all_books = await Book.objects.filter(genre="Fiction").all()
            assert len(all_books) == 3

            with pytest.raises(QueryDefinitionError):
                await Book.objects.delete()

            await Book.objects.delete(each=True)
            all_books = await Book.objects.all()
            assert len(all_books) == 0


@pytest.mark.asyncio
async def test_get_or_create():
    async with database:
        tom = await Book.objects.get_or_create(
            title="Volume I", author="Anonymous", genre="Fiction"
        )
        assert await Book.objects.count() == 1

        assert (
            await Book.objects.get_or_create(
                title="Volume I", author="Anonymous", genre="Fiction"
            )
            == tom
        )
        assert await Book.objects.count() == 1

        assert await Book.objects.create(
            title="Volume I", author="Anonymous", genre="Fiction"
        )
        with pytest.raises(ormar.exceptions.MultipleMatches):
            await Book.objects.get_or_create(
                title="Volume I", author="Anonymous", genre="Fiction"
            )


@pytest.mark.asyncio
async def test_update_or_create():
    async with database:
        tom = await Book.objects.update_or_create(
            title="Volume I", author="Anonymous", genre="Fiction"
        )
        assert await Book.objects.count() == 1

        assert await Book.objects.update_or_create(id=tom.id, genre="Historic")
        assert await Book.objects.count() == 1

        assert await Book.objects.update_or_create(pk=tom.id, genre="Fantasy")
        assert await Book.objects.count() == 1

        assert await Book.objects.create(
            title="Volume I", author="Anonymous", genre="Fantasy"
        )
        with pytest.raises(ormar.exceptions.MultipleMatches):
            await Book.objects.get(
                title="Volume I", author="Anonymous", genre="Fantasy"
            )


@pytest.mark.asyncio
async def test_bulk_create():
    async with database:
        await ToDo.objects.bulk_create(
            [
                ToDo(text="Buy the groceries."),
                ToDo(text="Call Mum.", completed=True),
                ToDo(text="Send invoices.", completed=True),
            ]
        )

        todoes = await ToDo.objects.all()
        assert len(todoes) == 3
        for todo in todoes:
            assert todo.pk is not None

        completed = await ToDo.objects.filter(completed=True).all()
        assert len(completed) == 2


@pytest.mark.asyncio
async def test_bulk_create_with_relation():
    async with database:
        category = await Category.objects.create(name="Sample Category")

        await Note.objects.bulk_create(
            [
                Note(text="Buy the groceries.", category=category),
                Note(text="Call Mum.", category=category),
            ]
        )

        todoes = await Note.objects.all()
        assert len(todoes) == 2
        for todo in todoes:
            assert todo.category.pk == category.pk


@pytest.mark.asyncio
async def test_bulk_update():
    async with database:
        await ToDo.objects.bulk_create(
            [
                ToDo(text="Buy the groceries."),
                ToDo(text="Call Mum.", completed=True),
                ToDo(text="Send invoices.", completed=True),
            ]
        )
        todoes = await ToDo.objects.all()
        assert len(todoes) == 3

        for todo in todoes:
            todo.text = todo.text + "_1"
            todo.completed = False

        await ToDo.objects.bulk_update(todoes)

        completed = await ToDo.objects.filter(completed=False).all()
        assert len(completed) == 3

        todoes = await ToDo.objects.all()
        assert len(todoes) == 3

        for todo in todoes:
            assert todo.text[-2:] == "_1"


@pytest.mark.asyncio
async def test_bulk_update_with_only_selected_columns():
    async with database:
        await ToDo.objects.bulk_create(
            [
                ToDo(text="Reset the world simulation.", completed=False),
                ToDo(text="Watch kittens.", completed=True),
            ]
        )

        todoes = await ToDo.objects.all()
        assert len(todoes) == 2

        for todo in todoes:
            todo.text = todo.text + "_1"
            todo.completed = False

        await ToDo.objects.bulk_update(todoes, columns=["completed"])

        completed = await ToDo.objects.filter(completed=False).all()
        assert len(completed) == 2

        todoes = await ToDo.objects.all()
        assert len(todoes) == 2

        for todo in todoes:
            assert todo.text[-2:] != "_1"


@pytest.mark.asyncio
async def test_bulk_update_with_relation():
    async with database:
        category = await Category.objects.create(name="Sample Category")
        category2 = await Category.objects.create(name="Sample II Category")

        await Note.objects.bulk_create(
            [
                Note(text="Buy the groceries.", category=category),
                Note(text="Call Mum.", category=category),
                Note(text="Text skynet.", category=category),
            ]
        )

        notes = await Note.objects.all()
        assert len(notes) == 3

        for note in notes:
            note.category = category2

        await Note.objects.bulk_update(notes)

        notes_upd = await Note.objects.all()
        assert len(notes_upd) == 3

        for note in notes_upd:
            assert note.category.pk == category2.pk


@pytest.mark.asyncio
async def test_bulk_update_not_saved_objts():
    async with database:
        category = await Category.objects.create(name="Sample Category")
        with pytest.raises(ModelPersistenceError):
            await Note.objects.bulk_update(
                [
                    Note(text="Buy the groceries.", category=category),
                    Note(text="Call Mum.", category=category),
                ]
            )

        with pytest.raises(ModelListEmptyError):
            await Note.objects.bulk_update([])
