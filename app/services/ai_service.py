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


def call_ai(
    *,
    prompt: str,
    system_prompt: Optional[str] = None,
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
        payload = {
            "model": "gpt-4o-mini",  # or whatever your org allows
            "messages": [
                {"role": "user", "content": prompt}
            ],
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
            timeout=30,
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
                timeout=30,
            )

        # ----------------------------------------
        # 5. Error handling
        # ----------------------------------------
        if response.status_code != 200:
            return {
                "success": False,
                "response": None,
                "error": f"HTTP {response.status_code}: {response.text}",
            }

        data = response.json()

        # ----------------------------------------
        # 6. Normalize response (TEMP ASSUMPTION)
        # ----------------------------------------
        ai_text = data["choices"][0]["message"]["content"]

        return {
            "success": True,
            "response": ai_text,
            "error": None,
        }

    except Exception as e:
        return {
            "success": False,
            "response": None,
            "error": str(e),
        }