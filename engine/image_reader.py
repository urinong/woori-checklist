"""포장지 사진 OCR — Claude Vision API (우선) 또는 Tesseract (폴백)

포장지 사진에서 한국 식품 표시사항을 추출하여 dict 형태로 반환.
"""
from typing import Dict, Any, Optional
import os
import base64
import re
import json

from config import USE_CLAUDE_VISION


SYSTEM_PROMPT = """당신은 한국 식품 포장지 표시사항 전문가입니다.
사진에서 다음 항목을 한국어 그대로 추출하세요:
- 제품명
- 식품유형
- 제조원 (회사명 + 주소)
- 판매원 (회사명 + 주소)
- 소비기한
- 내용량
- 원재료 및 함량 (전체 원문)
- 알레르기물질
- 용기포장재질
- 품목보고번호
- 보관방법

JSON 형식으로만 응답하세요. 추출할 수 없는 항목은 null로 두세요.
"""


def read_label_image(image_path: str) -> Dict[str, Any]:
    """포장지 사진 → 표시사항 dict"""
    if USE_CLAUDE_VISION:
        try:
            return _read_with_claude(image_path)
        except Exception as e:
            print(f"[image_reader] Claude Vision 실패 → 폴백: {e}")
    return _read_with_tesseract(image_path)


# ---------------------------------------------------------------------------
# Claude Vision API
# ---------------------------------------------------------------------------

def _read_with_claude(image_path: str) -> Dict[str, Any]:
    import urllib.request
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 미설정")

    with open(image_path, "rb") as f:
        img_bytes = f.read()
    b64 = base64.standard_b64encode(img_bytes).decode()

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")

    body = {
        "model": "claude-3-5-sonnet-20241022",
        "max_tokens": 2000,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": "이 포장지 표시사항을 JSON으로 추출해주세요."},
            ],
        }],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    text = data["content"][0]["text"]
    # JSON 블록 추출
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        return json.loads(m.group(0))
    return {"raw": text}


# ---------------------------------------------------------------------------
# Tesseract 폴백
# ---------------------------------------------------------------------------

def _read_with_tesseract(image_path: str) -> Dict[str, Any]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return {
            "_error": "OCR 사용 불가. ANTHROPIC_API_KEY를 설정하거나 pytesseract를 설치하세요.",
            "raw": "",
        }
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(img, lang="kor+eng")
    except Exception as e:
        return {"_error": f"Tesseract OCR 실패: {e}", "raw": ""}
    return _parse_ocr_text(text)


def _parse_ocr_text(text: str) -> Dict[str, Any]:
    """Tesseract 원문에서 간단 파싱"""
    result = {"raw": text}
    patterns = {
        "제품명": r"제\s*품\s*명\s*[:：]?\s*([^\n]{2,40})",
        "식품유형": r"식품\s*유?형?\s*[:：]?\s*([^\n]{2,40})",
        "내용량": r"내\s*용\s*량\s*[:：]?\s*([^\n]{2,20})",
        "보관방법": r"보\s*관\s*방\s*법\s*[:：]?\s*([^\n]{2,30})",
        "알레르기물질": r"알\s*레\s*르\s*기\s*[:：]?\s*([^\n]{2,40})",
        "품목보고번호": r"품목[제보]*보고번호\s*[:：]?\s*([0-9]{8,20})",
    }
    for k, pat in patterns.items():
        m = re.search(pat, text)
        if m:
            result[k] = m.group(1).strip()
    return result
