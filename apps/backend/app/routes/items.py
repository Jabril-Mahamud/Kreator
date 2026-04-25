import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Item
from app.schemas import ItemCreate, ItemRead

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=list[ItemRead])
async def list_items(session: AsyncSession = Depends(get_session)) -> list[Item]:
    result = await session.execute(select(Item).order_by(Item.created_at.desc()))
    return list(result.scalars().all())


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate, session: AsyncSession = Depends(get_session)
) -> Item:
    item = Item(name=payload.name, description=payload.description)
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> Item:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    await session.delete(item)
    await session.commit()
