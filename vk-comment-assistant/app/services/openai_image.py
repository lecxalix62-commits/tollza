from __future__ import annotations

import base64
import os

import httpx
import openai


def generate_from_photo(photo_url: str, prompt: str) -> bytes:
    """Download VK photo, send to gpt-image-1, return generated PNG bytes."""
    resp = httpx.get(photo_url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    image_bytes = resp.content
    content_type = resp.headers.get("content-type", "image/jpeg")

    if "png" in content_type:
        filename = "image.png"
    elif "webp" in content_type:
        filename = "image.webp"
    else:
        filename = "image.jpg"

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
    response = client.images.edit(
        model="gpt-image-1",
        image=(filename, image_bytes, content_type),
        prompt=prompt,
        n=1,
        size="1024x1024",
    )
    return base64.b64decode(response.data[0].b64_json)
