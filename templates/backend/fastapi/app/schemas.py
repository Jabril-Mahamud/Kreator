import uuid

from pydantic import BaseModel


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None

    model_config = {"from_attributes": True}
