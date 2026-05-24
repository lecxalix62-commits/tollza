from __future__ import annotations

import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Response
from pydantic import BaseModel

from app.services.vk_client import (
    VKCaptchaRequired,
    create_comment,
    get_recent_posts,
    get_wall_comments,
    send_message,
)
from app.store import store

router = APIRouter(prefix="/autopilot", tags=["autopilot"])

_run_lock = threading.Lock()
_stop_event = threading.Event()
_scheduler_thread: threading.Thread | None = None


class AutopilotConfig(BaseModel):
    enabled: bool = False
    keywords: list[str] = []
    posts_per_community: int = 10
    interval_minutes: int = 60
    send_dm: bool = True
    dm_message: str = ""
    send_comment: bool = False
    comment_message: str = ""


class RunResult(BaseModel):
    run_at: str
    found: int
    dm_sent: int
    comment_sent: int
    skipped: int
    errors: list[str]


@router.get("/config", response_model=AutopilotConfig)
def get_config() -> AutopilotConfig:
    data = store.get_autopilot_config()
    return AutopilotConfig(**data) if data else AutopilotConfig()


@router.post("/config", response_model=AutopilotConfig)
def save_config(payload: AutopilotConfig) -> AutopilotConfig:
    store.save_autopilot_config(payload.model_dump())
    _restart_scheduler(payload)
    return payload


@router.post("/run", response_model=RunResult)
def run_now() -> RunResult:
    data = store.get_autopilot_config()
    config = AutopilotConfig(**data) if data else AutopilotConfig()
    return _do_run(config)


@router.get("/log", response_model=list[RunResult])
def get_log() -> list[RunResult]:
    return [RunResult(**e) for e in store.get_autopilot_log()]


@router.get("/contacted-count")
def contacted_count() -> dict:
    return {"count": store.count_autopilot_contacted()}


@router.delete("/contacted")
def clear_contacted() -> Response:
    store.clear_autopilot_contacted()
    return Response(status_code=204)


# ── Run logic ──────────────────────────────────────────────────────────────────

def _do_run(config: AutopilotConfig) -> RunResult:
    with _run_lock:
        run_at = datetime.now(timezone.utc).isoformat()
        found = dm_sent = comment_sent = skipped = 0
        errors: list[str] = []

        keywords = [kw.strip().lower() for kw in config.keywords if kw.strip()]
        if not keywords:
            result = RunResult(run_at=run_at, found=0, dm_sent=0, comment_sent=0,
                               skipped=0, errors=["Нет ключевых слов"])
            store.add_autopilot_log_entry(**result.model_dump())
            return result

        communities = store.list_communities()
        if not communities:
            result = RunResult(run_at=run_at, found=0, dm_sent=0, comment_sent=0,
                               skipped=0, errors=["Нет сообществ"])
            store.add_autopilot_log_entry(**result.model_dump())
            return result

        candidates: list[dict] = []

        for community in communities:
            owner_id = -community.vk_group_id
            try:
                posts = get_recent_posts(owner_id, count=config.posts_per_community)
            except Exception as exc:
                errors.append(f"{community.name}: {exc}")
                continue

            for post in posts:
                post_id = post["id"]
                from_id = post.get("from_id", 0)
                text = post.get("text", "")

                if from_id > 0 and any(kw in text.lower() for kw in keywords):
                    found += 1
                    candidates.append({"author_id": from_id, "owner_id": owner_id, "post_id": post_id})

                try:
                    for comment in get_wall_comments(owner_id, post_id):
                        c_from = comment.get("from_id", 0)
                        c_text = comment.get("text", "")
                        if c_from > 0 and any(kw in c_text.lower() for kw in keywords):
                            found += 1
                            candidates.append({"author_id": c_from, "owner_id": owner_id, "post_id": post_id})
                except Exception:
                    pass

        contacted = store.get_autopilot_contacted()
        seen_dm: set[int] = set()
        seen_comment: set[tuple] = set()
        sending_blocked_by_captcha = False

        for c in candidates:
            if sending_blocked_by_captcha:
                skipped += 1
                continue

            author_id = c["author_id"]
            post_key = (c["owner_id"], c["post_id"])

            if config.send_dm and config.dm_message:
                if author_id not in contacted and author_id not in seen_dm:
                    try:
                        send_message(author_id, config.dm_message)
                        dm_sent += 1
                        seen_dm.add(author_id)
                        store.add_autopilot_contacted(author_id)
                    except VKCaptchaRequired as exc:
                        errors.append(f"ЛС {author_id}: {exc}")
                        errors.append("Отправка остановлена до ручного решения капчи VK")
                        sending_blocked_by_captcha = True
                    except Exception as exc:
                        errors.append(f"ЛС {author_id}: {exc}")
                else:
                    skipped += 1

            if sending_blocked_by_captcha:
                continue

            if config.send_comment and config.comment_message:
                if post_key not in seen_comment:
                    try:
                        create_comment(c["owner_id"], c["post_id"], config.comment_message)
                        comment_sent += 1
                        seen_comment.add(post_key)
                    except VKCaptchaRequired as exc:
                        errors.append(f"Комментарий {post_key}: {exc}")
                        errors.append("Отправка остановлена до ручного решения капчи VK")
                        sending_blocked_by_captcha = True
                    except Exception as exc:
                        errors.append(f"Комментарий {post_key}: {exc}")

        store.add_autopilot_log_entry(run_at, found, dm_sent, comment_sent, skipped, errors)
        return RunResult(run_at=run_at, found=found, dm_sent=dm_sent,
                         comment_sent=comment_sent, skipped=skipped, errors=errors)


# ── Scheduler ──────────────────────────────────────────────────────────────────

def _scheduler_loop(interval_seconds: int) -> None:
    _stop_event.wait(interval_seconds)
    while not _stop_event.is_set():
        data = store.get_autopilot_config()
        config = AutopilotConfig(**data) if data else AutopilotConfig()
        if config.enabled:
            try:
                _do_run(config)
            except Exception:
                pass
        _stop_event.wait(config.interval_minutes * 60)


def _restart_scheduler(config: AutopilotConfig) -> None:
    global _scheduler_thread
    _stop_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=2)
    _stop_event.clear()
    if config.enabled and config.interval_minutes > 0:
        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(config.interval_minutes * 60,),
            daemon=True,
            name="autopilot-scheduler",
        )
        _scheduler_thread.start()


def start_scheduler() -> None:
    data = store.get_autopilot_config()
    if data:
        _restart_scheduler(AutopilotConfig(**data))
