"""Gemini 呼叫的薄封裝。

三個重點：
1. 每次呼叫都重新從 prompts/ 讀 system prompt（規格要求）。
2. 每次呼叫都重新從 models.yaml 讀該角色要用的模型 ID。
3. 一律要求 JSON 輸出，並在解析失敗時重試 / 修補。
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from google import genai
from google.genai import types

from config import GEMINI_API_KEY, load_prompt, model_for, option

_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("缺少 GEMINI_API_KEY，請在專案根目錄的 .env 填入")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.MULTILINE)


def _parse_json(text: str) -> Any:
    cleaned = _FENCE.sub("", text or "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 退而求其次：抓最外層的 {...} 或 [...]
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = cleaned.find(opener), cleaned.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(cleaned[i:j + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"模型沒有回傳合法 JSON：{cleaned[:400]}")


async def call_json(
    role: str,
    prompt_file: str,
    user_text: str,
    image_png: bytes | None = None,
    temperature: float = 0.2,
    extra_system: str = "",
) -> Any:
    """呼叫 Gemini 並回傳解析後的 JSON。

    role         -> models.yaml 裡的角色名稱
    prompt_file  -> prompts/ 底下的檔名，內容作為 system_instruction
    """
    model = model_for(role)
    system = load_prompt(prompt_file)
    if extra_system:
        system = f"{system}\n\n{extra_system}"

    parts: list[Any] = []
    if image_png is not None:
        parts.append(types.Part.from_bytes(data=image_png, mime_type="image/png"))
    parts.append(types.Part.from_text(text=user_text))

    cfg = types.GenerateContentConfig(
        system_instruction=system,
        response_mime_type="application/json",
        temperature=temperature,
    )

    retries = int(option("max_retries", 2))
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            resp = await client().aio.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=cfg,
            )
            return _parse_json(resp.text or "")
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                await asyncio.sleep(0.8 * (attempt + 1))

    raise RuntimeError(f"[{role} / {model}] 呼叫失敗：{last_err}")


async def call_image(role: str, prompt_file: str, user_text: str,
                     ref_images: list[bytes] | None = None) -> bytes | None:
    """呼叫影像生成模型（選用路徑）。回傳 PNG bytes，失敗回 None。"""
    model = model_for(role)
    system = load_prompt(prompt_file)

    parts: list[Any] = []
    for img in (ref_images or []):
        parts.append(types.Part.from_bytes(data=img, mime_type="image/png"))
    parts.append(types.Part.from_text(text=f"{system}\n\n{user_text}"))

    try:
        resp = await client().aio.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=parts)],
            # 用 TEXT+IMAGE 而非只有 IMAGE：部分影像模型不接受純 IMAGE 的 modality
            config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
        )
        for cand in resp.candidates or []:
            for part in cand.content.parts or []:
                inline = getattr(part, "inline_data", None)
                if inline and inline.data:
                    return inline.data
    except Exception:
        return None
    return None
