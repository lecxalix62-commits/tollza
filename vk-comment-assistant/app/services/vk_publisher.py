from __future__ import annotations

from app.models import Community, CommentDraft, DraftStatus, PublishResult
from app.services.vk_client import VKCaptchaRequired, create_comment, get_recent_posts

POSTS_PER_COMMUNITY = 3


def publish_draft(
    draft: CommentDraft,
    communities: list[Community],
) -> tuple[DraftStatus, list[PublishResult]]:
    results: list[PublishResult] = []
    stop_on_captcha = False

    for community in communities:
        if stop_on_captcha:
            break

        owner_id = -community.vk_group_id
        try:
            posts = get_recent_posts(owner_id, count=POSTS_PER_COMMUNITY)
        except Exception as exc:
            results.append(
                PublishResult(
                    vk_owner_id=owner_id,
                    vk_post_id=0,
                    error=f"Ошибка получения постов [{community.name}]: {exc}",
                )
            )
            continue

        for post in posts:
            post_id = post["id"]
            try:
                comment_id = create_comment(owner_id, post_id, draft.text, draft.image_attachment)
                results.append(
                    PublishResult(
                        vk_owner_id=owner_id,
                        vk_post_id=post_id,
                        comment_id=comment_id,
                    )
                )
            except VKCaptchaRequired as exc:
                results.append(
                    PublishResult(
                        vk_owner_id=owner_id,
                        vk_post_id=post_id,
                        error=str(exc),
                        captcha_challenge_id=exc.challenge_id,
                    )
                )
                stop_on_captcha = True
                break
            except Exception as exc:
                results.append(
                    PublishResult(
                        vk_owner_id=owner_id,
                        vk_post_id=post_id,
                        error=str(exc),
                    )
                )

    has_success = any(r.comment_id is not None for r in results)
    all_failed = all(r.error is not None for r in results) if results else True

    status = DraftStatus.publish_failed if (not results or all_failed) else DraftStatus.published
    return status, results
