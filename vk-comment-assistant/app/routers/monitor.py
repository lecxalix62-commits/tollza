from __future__ import annotations

import base64

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.vk_client import get_recent_posts, get_wall_comments, get_users, send_message, upload_photo_wall
from app.store import store

router = APIRouter(prefix="/monitor", tags=["monitor"])


class ScanRequest(BaseModel):
    keywords: list[str]
    posts_per_community: int = 10


class ScanResult(BaseModel):
    community: str
    community_screen_name: str
    author_id: int
    author_name: str
    text: str
    type: str          # "пост" | "комментарий"
    post_id: int = 0
    owner_id: int = 0
    date: int = 0      # unix timestamp
    likes: int = 0
    comments_count: int = 0
    vk_link: str = ""
    photo_urls: list[str] = []


def _extract_photos(attachments: list[dict]) -> list[str]:
    urls = []
    for att in attachments:
        if att.get("type") == "photo":
            sizes = att["photo"].get("sizes", [])
            if sizes:
                best = max(sizes, key=lambda s: s.get("width", 0))
                url = best.get("url", "")
                if url:
                    urls.append(url)
    return urls


class DmRequest(BaseModel):
    user_id: int
    message: str
    attachment: str | None = None


@router.post("/scan", response_model=list[ScanResult])
def scan(payload: ScanRequest) -> list[ScanResult]:
    communities = store.list_communities()
    if not communities:
        return []
    keywords = [kw.strip().lower() for kw in payload.keywords if kw.strip()]
    if not keywords:
        return []

    raw: list[dict] = []

    for community in communities:
        owner_id = -community.vk_group_id
        try:
            posts = get_recent_posts(owner_id, count=payload.posts_per_community)
        except Exception:
            continue

        for post in posts:
            post_id = post["id"]
            from_id = post.get("from_id", 0)
            text = post.get("text", "")

            if from_id > 0 and any(kw in text.lower() for kw in keywords):
                raw.append({
                    "community": community.name,
                    "community_screen_name": community.screen_name,
                    "author_id": from_id,
                    "author_name": "",
                    "text": text,
                    "type": "пост",
                    "post_id": post_id,
                    "owner_id": owner_id,
                    "date": post.get("date", 0),
                    "likes": post.get("likes", {}).get("count", 0),
                    "comments_count": post.get("comments", {}).get("count", 0),
                    "vk_link": f"https://vk.com/wall{owner_id}_{post_id}",
                    "photo_urls": _extract_photos(post.get("attachments", [])),
                })

            try:
                comments = get_wall_comments(owner_id, post_id)
                for comment in comments:
                    c_from = comment.get("from_id", 0)
                    c_text = comment.get("text", "")
                    c_id = comment.get("id", 0)
                    if c_from > 0 and any(kw in c_text.lower() for kw in keywords):
                        raw.append({
                            "community": community.name,
                            "community_screen_name": community.screen_name,
                            "author_id": c_from,
                            "author_name": "",
                            "text": c_text,
                            "type": "комментарий",
                            "post_id": post_id,
                            "owner_id": owner_id,
                            "date": comment.get("date", 0),
                            "likes": comment.get("likes", {}).get("count", 0),
                            "comments_count": 0,
                            "vk_link": f"https://vk.com/wall{owner_id}_{post_id}?reply={c_id}",
                            "photo_urls": _extract_photos(comment.get("attachments", [])),
                        })
            except Exception:
                pass

    if raw:
        ids = list({r["author_id"] for r in raw})
        try:
            users = get_users(ids)
            name_map = {u["id"]: f"{u['first_name']} {u['last_name']}" for u in users}
            for r in raw:
                r["author_name"] = name_map.get(r["author_id"], str(r["author_id"]))
        except Exception:
            for r in raw:
                r["author_name"] = str(r["author_id"])

    return [ScanResult(**r) for r in raw]


@router.post("/send-dm")
def send_dm(payload: DmRequest) -> dict:
    try:
        send_message(payload.user_id, payload.message, payload.attachment)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class GenerateImageRequest(BaseModel):
    photo_url: str
    prompt: str
    provider: str = "nanobanana"  # "openai" | "nanobanana"


@router.post("/generate-image")
def generate_image(payload: GenerateImageRequest) -> dict:
    if payload.provider == "nanobanana":
        from app.services.nanobanana_image import generate_from_photo
        provider_label = "NanoBanana"
    else:
        from app.services.openai_image import generate_from_photo
        provider_label = "OpenAI"

    try:
        img_bytes = generate_from_photo(payload.photo_url, payload.prompt)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{provider_label} ошибка: {exc}")
    try:
        attachment = upload_photo_wall(img_bytes, "generated.png")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"VK upload ошибка: {exc}")
    return {
        "attachment": attachment,
        "image_b64": base64.b64encode(img_bytes).decode(),
    }


@router.post("/nb-callback")
def nb_callback(data: dict = None) -> dict:
    """No-op callback endpoint for NanoBanana webhook (we use polling instead)."""
    return {"ok": True}
