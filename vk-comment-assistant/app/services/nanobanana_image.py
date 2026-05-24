from __future__ import annotations

import os
import time

import httpx

API_BASE = "https://api.nanobananaapi.ai/api/v1/nanobanana"
POLL_INTERVAL = 3   # seconds between polls
MAX_POLLS = 60      # up to ~3 minutes


def generate_from_photo(photo_url: str, prompt: str) -> bytes:
    """Submit image-to-image task to NanoBanana, poll until done, return image bytes."""
    api_key = os.getenv("NANOBANANA_API_KEY", "")
    if not api_key:
        raise RuntimeError("NANOBANANA_API_KEY не задан в .env")

    headers = {"Authorization": f"Bearer {api_key}"}

    # Submit task
    resp = httpx.post(
        f"{API_BASE}/generate",
        headers=headers,
        json={
            "prompt": prompt,
            "type": "IMAGETOIAMGE",
            "callBackUrl": "http://localhost:8000/monitor/nb-callback",
            "imageUrls": [photo_url],
            "numImages": 1,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"NanoBanana: {data.get('msg', 'ошибка запроса')}")

    task_id = data["data"]["taskId"]

    # Poll for result
    for _ in range(MAX_POLLS):
        time.sleep(POLL_INTERVAL)
        poll = httpx.get(
            f"{API_BASE}/record-info",
            headers=headers,
            params={"taskId": task_id},
            timeout=15,
        )
        poll.raise_for_status()
        pdata = poll.json()
        if pdata.get("code") != 200:
            raise RuntimeError(f"NanoBanana poll: {pdata.get('msg')}")

        record = pdata["data"]
        flag = record.get("successFlag", 0)

        if flag == 1:
            result_url = record["response"]["resultImageUrl"]
            img = httpx.get(result_url, timeout=30, follow_redirects=True)
            img.raise_for_status()
            return img.content
        elif flag in (2, 3):
            raise RuntimeError(f"Генерация не удалась: {record.get('errorMessage', 'unknown')}")
        # flag == 0: ещё генерирует, ждём

    raise RuntimeError("Таймаут генерации (3 мин)")
