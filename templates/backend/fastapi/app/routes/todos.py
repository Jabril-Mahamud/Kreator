import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import get_current_user_id
from app.database import async_session
from app.models import Todo

router = APIRouter(prefix="/api/todos", tags=["todos"])


class TodoCreate(BaseModel):
    title: str
    description: str | None = None


class TodoUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    completed: bool | None = None


class TodoResponse(BaseModel):
    id: str
    title: str
    description: str | None
    completed: bool
    created_at: str


@router.get("", response_model=list[TodoResponse])
async def list_todos(user_id: str = Depends(get_current_user_id)) -> list[TodoResponse]:
    async with async_session() as session:
        result = await session.execute(
            select(Todo).where(Todo.user_id == uuid.UUID(user_id)).order_by(Todo.created_at.desc())
        )
        todos = result.scalars().all()
        return [
            TodoResponse(
                id=str(t.id),
                title=t.title,
                description=t.description,
                completed=t.completed,
                created_at=t.created_at.isoformat(),
            )
            for t in todos
        ]


@router.post("", response_model=TodoResponse, status_code=status.HTTP_201_CREATED)
async def create_todo(
    body: TodoCreate, user_id: str = Depends(get_current_user_id)
) -> TodoResponse:
    async with async_session() as session:
        todo = Todo(
            id=uuid.uuid4(),
            user_id=uuid.UUID(user_id),
            title=body.title,
            description=body.description,
        )
        session.add(todo)
        await session.commit()
        await session.refresh(todo)
        return TodoResponse(
            id=str(todo.id),
            title=todo.title,
            description=todo.description,
            completed=todo.completed,
            created_at=todo.created_at.isoformat(),
        )


@router.get("/{todo_id}", response_model=TodoResponse)
async def get_todo(todo_id: str, user_id: str = Depends(get_current_user_id)) -> TodoResponse:
    async with async_session() as session:
        result = await session.execute(
            select(Todo).where(Todo.id == uuid.UUID(todo_id), Todo.user_id == uuid.UUID(user_id))
        )
        todo = result.scalar_one_or_none()
        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
        return TodoResponse(
            id=str(todo.id),
            title=todo.title,
            description=todo.description,
            completed=todo.completed,
            created_at=todo.created_at.isoformat(),
        )


@router.patch("/{todo_id}", response_model=TodoResponse)
async def update_todo(
    todo_id: str, body: TodoUpdate, user_id: str = Depends(get_current_user_id)
) -> TodoResponse:
    async with async_session() as session:
        result = await session.execute(
            select(Todo).where(Todo.id == uuid.UUID(todo_id), Todo.user_id == uuid.UUID(user_id))
        )
        todo = result.scalar_one_or_none()
        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
        if body.title is not None:
            todo.title = body.title
        if body.description is not None:
            todo.description = body.description
        if body.completed is not None:
            todo.completed = body.completed
        await session.commit()
        await session.refresh(todo)
        return TodoResponse(
            id=str(todo.id),
            title=todo.title,
            description=todo.description,
            completed=todo.completed,
            created_at=todo.created_at.isoformat(),
        )


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(todo_id: str, user_id: str = Depends(get_current_user_id)) -> None:
    async with async_session() as session:
        result = await session.execute(
            select(Todo).where(Todo.id == uuid.UUID(todo_id), Todo.user_id == uuid.UUID(user_id))
        )
        todo = result.scalar_one_or_none()
        if not todo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Todo not found")
        await session.delete(todo)
        await session.commit()
