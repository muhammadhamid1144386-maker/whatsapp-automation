from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.db import db, oid
from core.security import audit, get_current_user, tenant
from models import MenuAddon, MenuCategory, MenuItem

router = APIRouter(prefix="/api/menu", tags=["menu"])


class CategoryBody(BaseModel):
    name: str
    sort_order: int = 0
    active: bool = True


class ItemBody(BaseModel):
    category_id: str
    name: str
    description: Optional[str] = None
    price: float
    image_url: Optional[str] = None
    available: bool = True
    addon_ids: List[str] = []
    sort_order: int = 0


class ItemPatch(BaseModel):
    category_id: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    image_url: Optional[str] = None
    available: Optional[bool] = None
    addon_ids: Optional[List[str]] = None
    sort_order: Optional[int] = None


class AddonBody(BaseModel):
    name: str
    price: float
    available: bool = True


@router.get("")
async def list_menu(restaurant_id: str = Depends(tenant)):
    categories = await db.menu_categories.find({"restaurant_id": restaurant_id}).sort("sort_order", 1).to_list(100)
    items = await db.menu_items.find({"restaurant_id": restaurant_id}).sort("sort_order", 1).to_list(500)
    addons = await db.menu_addons.find({"restaurant_id": restaurant_id}).to_list(100)
    return {
        "categories": [MenuCategory.from_mongo(c).model_dump() for c in categories],
        "items": [MenuItem.from_mongo(i).model_dump() for i in items],
        "addons": [MenuAddon.from_mongo(a).model_dump() for a in addons],
    }


@router.post("/categories")
async def create_category(body: CategoryBody, restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    doc = MenuCategory(restaurant_id=restaurant_id, **body.model_dump())
    result = await db.menu_categories.insert_one(doc.to_mongo())
    await audit(restaurant_id, user["email"], "menu.category.create", {"name": body.name})
    return MenuCategory.from_mongo(await db.menu_categories.find_one({"_id": result.inserted_id})).model_dump()


@router.put("/categories/{category_id}")
async def update_category(category_id: str, body: CategoryBody, restaurant_id: str = Depends(tenant)):
    result = await db.menu_categories.update_one(
        {"_id": oid(category_id), "restaurant_id": restaurant_id}, {"$set": body.model_dump()}
    )
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Category not found")
    return MenuCategory.from_mongo(await db.menu_categories.find_one({"_id": oid(category_id)})).model_dump()


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str, restaurant_id: str = Depends(tenant)):
    if await db.menu_items.count_documents({"restaurant_id": restaurant_id, "category_id": category_id}):
        raise HTTPException(status_code=400, detail="Remove the items in this category first")
    result = await db.menu_categories.delete_one({"_id": oid(category_id), "restaurant_id": restaurant_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Category not found")
    return {"ok": True}


@router.post("/items")
async def create_item(body: ItemBody, restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    if not await db.menu_categories.find_one({"_id": oid(body.category_id), "restaurant_id": restaurant_id}):
        raise HTTPException(status_code=400, detail="Unknown category")
    doc = MenuItem(restaurant_id=restaurant_id, **body.model_dump())
    result = await db.menu_items.insert_one(doc.to_mongo())
    await audit(restaurant_id, user["email"], "menu.item.create", {"name": body.name, "price": body.price})
    return MenuItem.from_mongo(await db.menu_items.find_one({"_id": result.inserted_id})).model_dump()


@router.put("/items/{item_id}")
async def update_item(item_id: str, body: ItemPatch, restaurant_id: str = Depends(tenant), user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    result = await db.menu_items.update_one({"_id": oid(item_id), "restaurant_id": restaurant_id}, {"$set": updates})
    if not result.matched_count:
        raise HTTPException(status_code=404, detail="Item not found")
    await audit(restaurant_id, user["email"], "menu.item.update", {"item_id": item_id, **{k: str(v) for k, v in updates.items()}})
    return MenuItem.from_mongo(await db.menu_items.find_one({"_id": oid(item_id)})).model_dump()


@router.delete("/items/{item_id}")
async def delete_item(item_id: str, restaurant_id: str = Depends(tenant)):
    result = await db.menu_items.delete_one({"_id": oid(item_id), "restaurant_id": restaurant_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"ok": True}


@router.post("/addons")
async def create_addon(body: AddonBody, restaurant_id: str = Depends(tenant)):
    doc = MenuAddon(restaurant_id=restaurant_id, **body.model_dump())
    result = await db.menu_addons.insert_one(doc.to_mongo())
    return MenuAddon.from_mongo(await db.menu_addons.find_one({"_id": result.inserted_id})).model_dump()


@router.delete("/addons/{addon_id}")
async def delete_addon(addon_id: str, restaurant_id: str = Depends(tenant)):
    result = await db.menu_addons.delete_one({"_id": oid(addon_id), "restaurant_id": restaurant_id})
    if not result.deleted_count:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return {"ok": True}
