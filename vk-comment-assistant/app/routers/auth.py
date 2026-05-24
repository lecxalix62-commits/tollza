from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Body
from fastapi.responses import HTMLResponse, RedirectResponse

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"

VK_CLIENT_ID = os.getenv("VK_CLIENT_ID", "")
REDIRECT_URI = "http://localhost:8000/auth/callback"
SCOPE = "wall,photos,messages,offline"

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/vk")
def vk_login() -> RedirectResponse:
    url = (
        f"https://oauth.vk.com/authorize"
        f"?client_id={VK_CLIENT_ID}"
        f"&scope={SCOPE}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=token"
        f"&v=5.131"
    )
    return RedirectResponse(url)


@router.get("/callback")
def vk_callback() -> HTMLResponse:
    return HTMLResponse("""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  body{font-family:sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#F0F4FF}
  .card{background:#fff;border-radius:16px;padding:40px;text-align:center;box-shadow:0 8px 24px rgba(15,23,42,.1);max-width:400px}
  .spinner{width:32px;height:32px;border:3px solid #EFF6FF;border-top-color:#3B82F6;border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 16px}
  @keyframes spin{to{transform:rotate(360deg)}}
  h2{color:#0F172A;font-size:1.1rem;margin-bottom:8px}
  p{color:#64748B;font-size:.9rem}
  .err{color:#EF4444}
</style>
</head><body>
<div class="card">
  <div id="content">
    <div class="spinner"></div>
    <h2>Авторизация...</h2>
    <p>Сохраняем токен</p>
  </div>
</div>
<script>
const hash = new URLSearchParams(location.hash.slice(1));
const token = hash.get('access_token');
const error = hash.get('error');
if (error || !token) {
  document.getElementById('content').innerHTML =
    '<h2 class="err">Ошибка авторизации</h2><p>' + (error || 'Токен не получен') + '</p><br><a href="/">На главную</a>';
} else {
  fetch('/auth/save-token', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({token})
  }).then(r => r.ok ? r.json() : Promise.reject())
    .then(() => { window.location.href = '/app'; })
    .catch(() => {
      document.getElementById('content').innerHTML =
        '<h2 class="err">Ошибка сохранения</h2><p>Попробуй снова</p><br><a href="/">На главную</a>';
    });
}
</script>
</body></html>""")


@router.post("/save-token")
def save_token(token: str = Body(..., embed=True)) -> dict:
    if not token:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Token required")
    _save_token(token)
    return {"ok": True}


@router.get("/status")
def auth_status() -> dict:
    token = os.getenv("VK_ACCESS_TOKEN", "")
    return {"configured": bool(token), "token_preview": token[:8] + "..." if token else None}


def _save_token(token: str) -> None:
    os.environ["VK_ACCESS_TOKEN"] = token
    lines: list[str] = []
    if ENV_FILE.exists():
        lines = ENV_FILE.read_text().splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith("VK_ACCESS_TOKEN="):
            lines[i] = f"VK_ACCESS_TOKEN={token}"
            updated = True
            break

    if not updated:
        lines.append(f"VK_ACCESS_TOKEN={token}")

    ENV_FILE.write_text("\n".join(lines) + "\n")
