import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Item
from app.schemas import ItemCreate, ItemResponse, ItemUpdate

router = APIRouter(prefix="/api/items", tags=["items"])


@router.get("", response_model=list[ItemResponse])
async def list_items(db: AsyncSession = Depends(get_db)) -> list[Item]:
    result = await db.execute(select(Item))
    return list(result.scalars().all())


@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(payload: ItemCreate, db: AsyncSession = Depends(get_db)) -> Item:
    item = Item(**payload.model_dump())
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Item:
    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.patch("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: uuid.UUID, payload: ItemUpdate, db: AsyncSession = Depends(get_db)
) -> Item:
    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    item = await db.get(Item, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    await db.delete(item)
    await db.commit()
