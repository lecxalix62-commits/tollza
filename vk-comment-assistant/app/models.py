from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DraftStatus(str, Enum):
    pending_review = "pending_review"
    rejected = "rejected"
    published = "published"
    publish_failed = "publish_failed"


class CommunityCreate(BaseModel):
    vk_group_id: int
    screen_name: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)


class Community(CommunityCreate):
    id: str
    created_at: datetime


class PublishResult(BaseModel):
    vk_owner_id: int
    vk_post_id: int
    comment_id: int | None = None
    error: str | None = None
    captcha_challenge_id: str | None = None


class DraftCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    community_ids: list[str] = Field(min_length=1)
    image_attachment: str | None = None


class CommentDraft(BaseModel):
    id: str
    text: str
    community_ids: list[str]
    status: DraftStatus = DraftStatus.pending_review
    created_at: datetime
    moderation_note: str | None = None
    publish_results: list[PublishResult] = Field(default_factory=list)
    image_attachment: str | None = None  # VK attachment string, e.g. "photo123_456"


class DraftDecision(BaseModel):
    moderation_note: str | None = None
