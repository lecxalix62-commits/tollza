from fastapi import APIRouter, HTTPException, UploadFile, File, Response

from app.models import CommentDraft, DraftCreateRequest, DraftDecision, DraftStatus
from app.services.vk_client import VKCaptchaRequired, get_captcha_image, solve_captcha, upload_photo_wall
from app.services.vk_publisher import publish_draft
from app.store import store


router = APIRouter(prefix="/drafts", tags=["drafts"])


class CaptchaSolveRequest(DraftDecision):
    captcha_key: str
    challenge_id: str


@router.get("", response_model=list[CommentDraft])
def list_drafts(status: DraftStatus | None = None) -> list[CommentDraft]:
    drafts = store.list_drafts()
    if status is None:
        return drafts
    return [d for d in drafts if d.status == status]


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...)) -> dict:
    contents = await file.read()
    try:
        attachment = upload_photo_wall(contents, file.filename or "photo.jpg")
        return {"attachment": attachment}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("", response_model=CommentDraft, status_code=201)
def create_draft(payload: DraftCreateRequest) -> CommentDraft:
    for community_id in payload.community_ids:
        if store.get_community(community_id) is None:
            raise HTTPException(status_code=404, detail=f"Community {community_id} not found")
    return store.create_draft(payload.text, payload.community_ids, image_attachment=payload.image_attachment)


@router.delete("/{draft_id}")
def delete_draft(draft_id: str) -> Response:
    if not store.delete_draft(draft_id):
        raise HTTPException(status_code=404, detail="Draft not found")
    return Response(status_code=204)


@router.post("/{draft_id}/approve", response_model=CommentDraft)
def approve_draft(draft_id: str, payload: DraftDecision) -> CommentDraft:
    draft = store.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    if draft.status not in {DraftStatus.pending_review, DraftStatus.publish_failed}:
        raise HTTPException(status_code=400, detail="Draft cannot be published in its current status")

    communities = [
        c for c in (store.get_community(cid) for cid in draft.community_ids)
        if c is not None
    ]
    new_status, results = publish_draft(draft, communities)

    updated = draft.model_copy(update={
        "status": new_status,
        "moderation_note": payload.moderation_note,
        "publish_results": results,
    })
    return store.save_draft(updated)


@router.post("/{draft_id}/reject", response_model=CommentDraft)
def reject_draft(draft_id: str, payload: DraftDecision) -> CommentDraft:
    draft = store.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    updated = draft.model_copy(update={
        "status": DraftStatus.rejected,
        "moderation_note": payload.moderation_note,
    })
    return store.save_draft(updated)


@router.get("/captcha/{challenge_id}/image")
def captcha_image(challenge_id: str) -> Response:
    try:
        data, content_type = get_captcha_image(challenge_id)
        return Response(content=data, media_type=content_type)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{draft_id}/publish-results/{vk_owner_id}/{vk_post_id}/solve-captcha", response_model=CommentDraft)
def solve_publish_captcha(
    draft_id: str,
    vk_owner_id: int,
    vk_post_id: int,
    payload: CaptchaSolveRequest,
) -> CommentDraft:
    draft = store.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")

    target = next(
        (
            result for result in draft.publish_results
            if result.vk_owner_id == vk_owner_id
            and result.vk_post_id == vk_post_id
            and result.captcha_challenge_id == payload.challenge_id
        ),
        None,
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Captcha challenge not found for this publish result")

    new_results = list(draft.publish_results)
    idx = new_results.index(target)

    try:
        response = solve_captcha(payload.challenge_id, payload.captcha_key.strip())
        new_results[idx] = target.model_copy(update={
            "comment_id": response["comment_id"],
            "error": None,
            "captcha_challenge_id": None,
        })
    except VKCaptchaRequired as exc:
        new_results[idx] = target.model_copy(update={
            "error": str(exc),
            "captcha_challenge_id": exc.challenge_id,
        })
    except Exception as exc:
        new_results[idx] = target.model_copy(update={
            "error": str(exc),
            "captcha_challenge_id": None,
        })

    all_failed = all(r.error is not None for r in new_results) if new_results else True
    new_status = DraftStatus.publish_failed if (not new_results or all_failed) else DraftStatus.published
    updated = draft.model_copy(update={
        "status": new_status,
        "moderation_note": payload.moderation_note,
        "publish_results": new_results,
    })
    return store.save_draft(updated)
