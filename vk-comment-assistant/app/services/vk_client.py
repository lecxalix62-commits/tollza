from __future__ import annotations

import os
import random
import threading
import time
from uuid import uuid4

import httpx

VK_API_BASE = "https://api.vk.com/method"
VK_VERSION = "5.131"
VK_MIN_REQUEST_INTERVAL = 0.35
VK_RATE_LIMIT_RETRIES = 5

_rate_limit_lock = threading.Lock()
_last_request_at = 0.0
_captcha_lock = threading.Lock()
_captcha_challenges: dict[str, dict] = {}


class VKAPIError(RuntimeError):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"VK API ошибка {code}: {message}")
        self.code = code
        self.message = message


class VKCaptchaRequired(VKAPIError):
    def __init__(
        self,
        message: str,
        captcha_sid: str | None = None,
        captcha_img: str | None = None,
        challenge_id: str | None = None,
    ) -> None:
        suffix = f". Открой капчу: {captcha_img}" if captcha_img else ""
        super().__init__(14, f"{message}{suffix}")
        self.captcha_sid = captcha_sid
        self.captcha_img = captcha_img
        self.challenge_id = challenge_id


def _token() -> str:
    return os.getenv("VK_ACCESS_TOKEN", "")


def _wait_for_rate_limit_slot() -> None:
    global _last_request_at

    with _rate_limit_lock:
        now = time.monotonic()
        delay = VK_MIN_REQUEST_INTERVAL - (now - _last_request_at)
        if delay > 0:
            time.sleep(delay)
        _last_request_at = time.monotonic()


def _store_captcha_challenge(method: str, params: dict, captcha_sid: str | None, captcha_img: str | None) -> str:
    challenge_id = uuid4().hex
    with _captcha_lock:
        _captcha_challenges[challenge_id] = {
            "method": method,
            "params": {k: v for k, v in params.items() if k not in {"captcha_sid", "captcha_key"}},
            "captcha_sid": captcha_sid,
            "captcha_img": captcha_img,
            "created_at": time.time(),
        }
    return challenge_id


def get_captcha_image(challenge_id: str) -> tuple[bytes, str]:
    with _captcha_lock:
        challenge = _captcha_challenges.get(challenge_id)

    if not challenge or not challenge.get("captcha_img"):
        raise RuntimeError("Captcha challenge not found")

    response = httpx.get(challenge["captcha_img"], timeout=10, follow_redirects=True)
    if not response.content:
        raise RuntimeError("Не удалось загрузить изображение капчи")
    return response.content, response.headers.get("content-type", "image/png")


def solve_captcha(challenge_id: str, captcha_key: str) -> dict:
    with _captcha_lock:
        challenge = _captcha_challenges.get(challenge_id)

    if not challenge:
        raise RuntimeError("Captcha challenge not found")

    response = _call(
        challenge["method"],
        {
            **challenge["params"],
            "captcha_sid": challenge["captcha_sid"],
            "captcha_key": captcha_key,
        },
    )

    with _captcha_lock:
        _captcha_challenges.pop(challenge_id, None)

    return response


def _call(method: str, params: dict) -> dict:
    token = _token()
    if not token:
        raise RuntimeError("VK_ACCESS_TOKEN не задан в переменных окружения")

    for attempt in range(VK_RATE_LIMIT_RETRIES + 1):
        _wait_for_rate_limit_slot()
        response = httpx.get(
            f"{VK_API_BASE}/{method}",
            params={"access_token": token, "v": VK_VERSION, **params},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()

        if "error" not in data:
            return data["response"]

        error = data["error"]
        if error.get("error_code") == 6 and attempt < VK_RATE_LIMIT_RETRIES:
            time.sleep(0.5 * (attempt + 1) + random.uniform(0, 0.2))
            continue

        if error.get("error_code") == 14:
            challenge_id = _store_captcha_challenge(
                method,
                params,
                error.get("captcha_sid"),
                error.get("captcha_img"),
            )
            raise VKCaptchaRequired(
                error.get("error_msg", "Captcha needed"),
                captcha_sid=error.get("captcha_sid"),
                captcha_img=error.get("captcha_img"),
                challenge_id=challenge_id,
            )

        raise VKAPIError(error["error_code"], error["error_msg"])

    raise RuntimeError("VK API ошибка 6: Too many requests per second")


def get_recent_posts(owner_id: int, count: int = 3) -> list[dict]:
    """owner_id должен быть отрицательным для сообществ."""
    response = _call("wall.get", {"owner_id": owner_id, "count": count, "filter": "all"})
    return response.get("items", [])


def create_comment(owner_id: int, post_id: int, message: str, attachment: str | None = None) -> int:
    """Возвращает comment_id."""
    params: dict = {"owner_id": owner_id, "post_id": post_id, "message": message}
    if attachment:
        params["attachments"] = attachment
    response = _call("wall.createComment", params)
    return response["comment_id"]


def get_wall_comments(owner_id: int, post_id: int, count: int = 100) -> list[dict]:
    response = _call("wall.getComments", {"owner_id": owner_id, "post_id": post_id, "count": count})
    return response.get("items", [])


def get_users(user_ids: list[int]) -> list[dict]:
    if not user_ids:
        return []
    response = _call("users.get", {"user_ids": ",".join(str(i) for i in user_ids[:1000])})
    return response if isinstance(response, list) else []


def send_message(user_id: int, message: str, attachment: str | None = None) -> None:
    params: dict = {
        "user_id": user_id,
        "message": message,
        "random_id": random.randint(1, 2 ** 31),
    }
    if attachment:
        params["attachment"] = attachment
    _call("messages.send", params)


def resolve_group(screen_name_or_id: str) -> dict:
    """Resolve VK group by screen_name or numeric ID. Returns group dict."""
    response = _call("groups.getById", {"group_id": screen_name_or_id})
    if not response:
        raise RuntimeError("Группа не найдена")
    return response[0]


def search_groups(query: str, count: int = 20) -> list[dict]:
    """Search VK groups by query string."""
    response = _call("groups.search", {"q": query, "count": count, "type": "group"})
    return response.get("items", [])


def upload_photo_wall(file_bytes: bytes, filename: str) -> str:
    """Upload photo to VK wall, return attachment string like 'photo123_456'."""
    server_data = _call("photos.getWallUploadServer", {})
    upload_url = server_data["upload_url"]

    resp = httpx.post(
        upload_url,
        files={"photo": (filename, file_bytes, "image/jpeg")},
        timeout=30,
    )
    resp.raise_for_status()
    upload_result = resp.json()

    save_result = _call("photos.saveWallPhoto", {
        "photo": upload_result["photo"],
        "server": upload_result["server"],
        "hash": upload_result["hash"],
    })
    photo = save_result[0]
    return f"photo{photo['owner_id']}_{photo['id']}"
