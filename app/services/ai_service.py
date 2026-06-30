# app/services/ai_service.py

"""
AI Service Layer (LogiQ / Intranet AI)

Purpose:
- Centralized AI execution layer
- Uses token_manager for auth
- Keeps API logic isolated

Rules:
- NO business logic
- NO token logic duplication
- ONLY API interaction
"""

import requests
from typing import Optional

from app.config.config import (
    AI_CLIENT_ID,
    AI_CLIENT_SECRET,
    AI_TOKEN_URL,
    AI_API_URL,
)

from app.services.token_manager import get_access_token


def _clip_error_text(value: object, limit: int = 500) -> str:
    text = " ".join(str(value or "").strip().split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _extract_chat_completion_text(data: object) -> tuple[str | None, str | None]:
    if not isinstance(data, dict):
        return None, f"AI response JSON was {type(data).__name__}, expected dict"

    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        keys = ", ".join(sorted(str(key) for key in data.keys()))
        return None, f"AI missing_choices top_level_keys={keys or 'none'}"

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return None, f"AI first_choice_not_dict type={type(first_choice).__name__}"

    finish_reason = _clip_error_text(first_choice.get("finish_reason"), 120) or "none"

    message = first_choice.get("message")
    if not isinstance(message, dict):
        keys = ", ".join(sorted(str(key) for key in first_choice.keys()))
        return None, (
            "AI missing_message "
            f"finish_reason={finish_reason} "
            f"choice_keys={keys or 'none'}"
        )

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content, None

    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str) and item.strip():
                text_parts.append(item.strip())
                continue

            if not isinstance(item, dict):
                continue

            text_value = item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                text_parts.append(text_value.strip())
                continue

            content_value = item.get("content")
            if isinstance(content_value, str) and content_value.strip():
                text_parts.append(content_value.strip())

        ai_text = "\n".join(text_parts).strip()
        if ai_text:
            return ai_text, None

    message_keys = ", ".join(sorted(str(key) for key in message.keys()))
    choice_keys = ", ".join(sorted(str(key) for key in first_choice.keys()))
    content_type = type(content).__name__

    return None, (
        "AI empty_content "
        f"finish_reason={finish_reason} "
        f"content_type={content_type} "
        f"message_keys={message_keys or 'none'} "
        f"choice_keys={choice_keys or 'none'}"
    )


def call_ai(
    *,
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = "gpt-5.5",
    temperature: float = 0.7,
    max_tokens: int = 500,
) -> dict:
    """
    Generic AI call using internal API

    Returns:
        {
            "success": bool,
            "response": str | None,
            "error": str | None
        }
    """

    if not prompt:
        return {
            "success": False,
            "response": None,
            "error": "Empty prompt",
        }

    try:
        # ----------------------------------------
        # 1. Get access token (cached + safe)
        # ----------------------------------------
        token = get_access_token(
            AI_CLIENT_ID,
            AI_CLIENT_SECRET,
            AI_TOKEN_URL
        )

        # ----------------------------------------
        # 2. Build request
        # ----------------------------------------
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        messages.append({
            "role": "user",
            "content": prompt
        })

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        # ----------------------------------------
        # 3. Call AI API
        # ----------------------------------------
        response = requests.post(
            AI_API_URL,
            json=payload,
            headers=headers,
            timeout=180,
        )

        # ----------------------------------------
        # 4. Handle token expiry (retry once)
        # ----------------------------------------
        if response.status_code == 401:
            token = get_access_token(
                AI_CLIENT_ID,
                AI_CLIENT_SECRET,
                AI_TOKEN_URL,
                force_refresh=True
            )

            headers["Authorization"] = f"Bearer {token}"

            response = requests.post(
                AI_API_URL,
                json=payload,
                headers=headers,
                timeout=180,
            )

        # ----------------------------------------
        # 5. Error handling
        # ----------------------------------------
        if response.status_code != 200:
            return {
                "success": False,
                "response": None,
                "error": (
                    f"AI request failed with HTTP {response.status_code}: "
                    f"{_clip_error_text(response.text)}"
                ),
            }

        try:
            data = response.json()
        except ValueError as exc:
            return {
                "success": False,
                "response": None,
                "error": f"AI response was not valid JSON: {type(exc).__name__}",
            }

        # ----------------------------------------
        # 6. Normalize response
        # ----------------------------------------
        ai_text, shape_error = _extract_chat_completion_text(data)
        if shape_error:
            return {
                "success": False,
                "response": None,
                "error": shape_error,
            }

        return {
            "success": True,
            "response": ai_text,
            "error": None,
        }

    except requests.Timeout:
        return {
            "success": False,
            "response": None,
            "error": "AI request timed out",
        }

    except requests.RequestException as exc:
        return {
            "success": False,
            "response": None,
            "error": f"AI request transport failed: {type(exc).__name__}",
        }

    except Exception as exc:
        return {
            "success": False,
            "response": None,
            "error": f"AI request failed: {type(exc).__name__}",
        }