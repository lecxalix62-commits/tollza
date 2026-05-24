from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from app.models import Community, CommunityCreate
from app.services.vk_client import resolve_group, search_groups
from app.store import store

router = APIRouter(prefix="/communities", tags=["communities"])


class ResolveRequest(BaseModel):
    url: str


@router.get("", response_model=list[Community])
def list_communities() -> list[Community]:
    return store.list_communities()


@router.get("/search-vk")
def search_vk(q: str) -> list[dict]:
    if not q.strip():
        return []
    try:
        groups = search_groups(q.strip())
        return [
            {"id": g["id"], "name": g["name"], "screen_name": g.get("screen_name", str(g["id"]))}
            for g in groups
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/resolve", response_model=Community, status_code=201)
def add_by_url(payload: ResolveRequest) -> Community:
    raw = payload.url.strip()
    if not raw:
        raise HTTPException(status_code=400, detail="URL не указан")
    screen = re.sub(r"https?://(www\.)?vk\.com/", "", raw).strip("/")
    m = re.match(r"^(?:club|public|group)?(\d+)$", screen)
    lookup = m.group(1) if m else screen

    try:
        group = resolve_group(lookup)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Check duplicate
    existing = next((c for c in store.list_communities() if c.vk_group_id == group["id"]), None)
    if existing:
        raise HTTPException(status_code=409, detail=f"Уже добавлено: {existing.name}")

    return store.create_community(CommunityCreate(
        vk_group_id=group["id"],
        screen_name=group.get("screen_name", str(group["id"])),
        name=group["name"],
    ))


@router.post("", response_model=Community, status_code=201)
def create_community(payload: CommunityCreate) -> Community:
    return store.create_community(payload)


@router.delete("/{community_id}")
def delete_community(community_id: str) -> Response:
    if not store.delete_community(community_id):
        raise HTTPException(status_code=404, detail="Community not found")
    return Response(status_code=204)
