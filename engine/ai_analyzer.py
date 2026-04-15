"""AI 분석 엔진 — Claude API 기반 물품사양서·서류 분석

기존 규칙 기반 엔진(checklist_engine, doc_matcher, label_comparator)을
Claude API 단일 호출로 대체합니다.

특징:
- Prompt Caching: 규정 지식베이스를 cache_control으로 캐시 → 비용·속도 최적화
- 결과 캐시: 동일 파일 재업로드 시 캐시된 결과 즉시 반환
- force=True: 캐시 무시하고 재분석
"""
import os
import json
import hashlib
import urllib.request
import urllib.error
from pathlib import Path


API_KEY = os.environ.get("ANTHROPIC_API_KEY")
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8000

CACHE_DIR = Path("cache")


# ─────────────────────────────────────────────────
# 캐시 유틸
# ─────────────────────────────────────────────────

def _ensure_cache_dir():
    CACHE_DIR.mkdir(exist_ok=True)


def get_cache_key(*contents):
    """업로드된 파일 내용들의 해시로 캐시 키 생성 (앞 16자)"""
    combined = "".join(str(c) for c in contents)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:16]


def get_cached_result(cache_key: str):
    """캐시 HIT 시 dict 반환, MISS 시 None"""
    _ensure_cache_dir()
    p = CACHE_DIR / f"{cache_key}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def save_to_cache(cache_key: str, result: dict):
    _ensure_cache_dir()
    p = CACHE_DIR / f"{cache_key}.json"
    p.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────
# 지식베이스 & 시스템 프롬프트 로드
# ─────────────────────────────────────────────────

def load_knowledge_base() -> str:
    for candidate in ["data/01_규정_지식베이스_v2.md", "docs/01_규정_지식베이스_v2.md"]:
        p = Path(candidate)
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError("규정 지식베이스 파일을 찾을 수 없습니다 (data/ 또는 docs/)")


# ─────────────────────────────────────────────────
# Claude API 호출
# ─────────────────────────────────────────────────

def call_claude_api(system_prompt: str, knowledge_base: str,
                    user_message: str, images=None) -> dict:
    """
    Claude API 호출 (Prompt Caching 적용).

    system_messages:
      1. 시스템 프롬프트 (일반)
      2. 규정 지식베이스 (cache_control=ephemeral → 5분 캐시)

    반환: {"analysis": str, "usage": dict, "cached": False}
          또는 {"error": str}
    """
    if not API_KEY:
        return {
            "error": (
                "ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
                "AI 분석 기능을 사용하려면 환경변수에 API 키를 설정해주세요.\n"
                "Render 배포 시: Dashboard → Environment Variables → ANTHROPIC_API_KEY"
            )
        }

    system_messages = [
        {"type": "text", "text": system_prompt},
        {
            "type": "text",
            "text": f"## 우리농 생산규정 지식베이스\n\n{knowledge_base}",
            "cache_control": {"type": "ephemeral"},
        },
    ]

    user_content = []
    if images:
        for img in images:
            user_content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": img["data"],
                },
            })
    user_content.append({"type": "text", "text": user_message})

    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": system_messages,
        "messages": [{"role": "user", "content": user_content}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "prompt-caching-2024-07-31",
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text_parts = [b["text"] for b in result["content"] if b.get("type") == "text"]
            return {
                "analysis": "\n".join(text_parts),
                "usage": result.get("usage", {}),
                "cached": False,
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        return {"error": f"API 호출 실패 (HTTP {e.code}): {body}"}
    except Exception as e:
        return {"error": f"API 호출 중 오류: {e}"}


# ─────────────────────────────────────────────────
# 기능 A: 빠른 진단
# ─────────────────────────────────────────────────

def analyze_quick_diagnosis(pdf_text=None, images=None, force=False) -> dict:
    """
    기능 A: 물품사양서 PDF 텍스트 또는 포장지 이미지로 빠른 진단.

    force=True: 캐시 무시하고 재분석
    """
    kb = load_knowledge_base()

    # 캐시 키: 이미지는 실제 데이터 길이로 구분
    img_sig = str(sum(len(i["data"]) for i in images)) if images else "no_img"
    cache_key = get_cache_key(pdf_text or "", img_sig)

    if not force:
        cached = get_cached_result(cache_key)
        if cached:
            cached["cached"] = True
            cached["cache_key"] = cache_key
            return cached

    # 사용자 메시지 구성
    if pdf_text and images:
        user_msg = (
            "다음은 신규 물품의 포장지 사진과 물품사양서입니다.\n"
            "기능 A(빠른 진단)를 수행해주세요.\n\n"
            f"[물품사양서 내용]\n{pdf_text}\n\n"
            "포장지 사진도 함께 첨부되어 있습니다. 포장지의 표시사항도 함께 분석해주세요."
        )
    elif pdf_text:
        user_msg = (
            "다음은 신규 물품의 물품사양서입니다.\n"
            "기능 A(빠른 진단)를 수행해주세요.\n\n"
            f"[물품사양서 내용]\n{pdf_text}"
        )
    elif images:
        user_msg = (
            "다음은 신규 물품의 포장지 사진입니다.\n"
            "기능 A(빠른 진단)를 수행해주세요.\n"
            "포장지의 표시사항을 읽고 분석해주세요."
        )
    else:
        return {"error": "분석할 파일이 없습니다. 물품사양서 PDF 또는 포장지 사진을 업로드해주세요."}

    result = call_claude_api(SYSTEM_PROMPT_WEBAPP, kb, user_msg, images)
    if "error" not in result:
        result["cache_key"] = cache_key
        save_to_cache(cache_key, result)
    return result


# ─────────────────────────────────────────────────
# 기능 B: 서류 검증
# ─────────────────────────────────────────────────

def analyze_document_verification(pdf_text: str, supporting_docs_text: str,
                                   images=None, force=False) -> dict:
    """
    기능 B: 물품사양서 + 증빙서류 + 포장지 사진으로 서류 검증.

    force=True: 캐시 무시하고 재분석
    """
    kb = load_knowledge_base()

    img_sig = str(sum(len(i["data"]) for i in images)) if images else "no_img"
    cache_key = get_cache_key(pdf_text, supporting_docs_text, img_sig)

    if not force:
        cached = get_cached_result(cache_key)
        if cached:
            cached["cached"] = True
            cached["cache_key"] = cache_key
            return cached

    user_msg = (
        "다음은 신규 물품의 물품사양서와 증빙서류입니다.\n"
        "기능 B(서류 검증)를 수행해주세요.\n\n"
        f"[물품사양서 내용]\n{pdf_text}\n\n"
        f"[증빙서류 내용]\n{supporting_docs_text}"
    )
    if images:
        user_msg += (
            "\n\n포장지 사진도 함께 첨부되어 있습니다. "
            "포장지의 표시사항과 물품사양서의 내용 일치 여부도 검증해주세요."
        )

    result = call_claude_api(SYSTEM_PROMPT_WEBAPP, kb, user_msg, images)
    if "error" not in result:
        result["cache_key"] = cache_key
        save_to_cache(cache_key, result)
    return result


# ─────────────────────────────────────────────────
# 웹앱용 시스템 프롬프트
# ─────────────────────────────────────────────────

SYSTEM_PROMPT_WEBAPP = """
당신은 가톨릭농민회/우리농촌살리기운동본부의 **신규물품 출하 준비 자가진단 도우미**입니다.
지역 교구 우리농 생산소비 담당 실무자가 사용하며, 신입직원도 이해할 수 있도록 친절하게 설명합니다.

## 두 가지 기능

### 기능 A: 빠른 진단
포장지 사진이나 물품사양서를 받으면, 출하에 필요한 서류와 주의사항을 안내합니다.

출력 형식 (반드시 이 구조를 따르세요):

#### 📦 제품 기본정보
제품명, 식품유형, 교구, 생산자, 회원구분, 제조원 등을 정리합니다.

#### 📋 출하에 필요한 서류 체크리스트
각 서류에 대해:
- 서류명
- 왜 필요한지 (신입직원도 이해할 수 있는 설명)
- 이 제품에서 특별히 주의할 점

필수 서류와 이 제품의 특성에 따른 조건부 서류를 구분하여 표시합니다.

#### ⚠️ 주의사항
원재료, 첨가물, 표시사항 등에서 발견된 이슈를 설명합니다.
각 항목에 대해:
- 무엇이 문제인지
- 왜 문제인지 (규정 근거)
- 어떻게 해결하면 되는지

우리농 규정에서 직접 다루지 않더라도, 국가 유기가공식품 인증 기준상
논의가 필요하거나 이슈 가능성이 있다면 반드시 포함합니다.

원재료가 원부재료/첨가물/향신료 중 어디에 해당하는지 애매한 경우
(예: 바나나농축분말처럼 농산물 가공품이면서 제품명에 포함된 경우),
각 분류별 적용 기준 차이를 설명하고 위원회 논의를 권고합니다.

#### 📨 생산자에게 요청할 사항
실무자가 복사하여 생산자에게 바로 전달할 수 있는 형태로 작성합니다.
"[생산자명] 님께," 로 시작하여 필요한 서류와 보완 사항을 번호 목록으로 정리합니다.

---

### 기능 B: 서류 검증
물품사양서 + 증빙서류(+ 선택적으로 포장지 사진)를 받으면 검증합니다.

출력 형식 (반드시 이 구조를 따르세요):

#### 1️⃣ 포장지 ↔ 물품사양서 대조 (포장지 사진이 있는 경우만)
항목별로 일치/불일치를 테이블로 정리합니다.

#### 2️⃣ 물품사양서 기재 점검
20개 필수 항목의 기재 여부를 점검합니다.
미기재/오류 항목에 대해 무엇을 어떻게 보완해야 하는지 설명합니다.

#### 3️⃣ 증빙서류 점검
각 필요 서류의 제출/미제출 여부를 표시합니다.
제출된 서류에 대해:
- 제품명이 물품사양서와 일치하는지
- 유효기간이 남아있는지
- 검사 결과가 적합한지
문제가 발견되면 구체적으로 설명합니다.

#### 4️⃣ 출하 승인 시 예상 이슈
전국물품위원회 심의에서 논의될 수 있는 사항을 미리 알려줍니다.
실무자가 사전에 대비할 수 있도록 합니다.

#### 📨 추가 요청이 필요한 서류
미제출 서류와 보완 사항을 생산자에게 전달할 수 있는 형태로 정리합니다.

---

## 분석 원칙

1. **규정 근거주의**: 판단의 근거를 규정 조항으로 명시합니다.
2. **보수적 판단**: 확실하지 않으면 "확인 필요"로 표시합니다.
3. **친절한 설명**: 모든 항목에 신입직원도 이해할 수 있는 설명을 달아줍니다.
4. **놓치지 않기**: 규정에 명시적 근거가 없는 이슈라도, 출하 승인 과정에서
   문제될 가능성이 조금이라도 있으면 주의사항에 포함합니다.
5. **실무 지향**: "어떻게 해결하면 되는지"를 반드시 함께 안내합니다.

## 응답 형식
- 마크다운 형식으로 작성합니다 (웹앱에서 렌더링됨)
- 이모지를 적절히 사용하여 가독성을 높입니다 (✅ ⚠️ ❌ 💡 📋 📨 📦)
- 테이블이 필요한 곳에는 마크다운 테이블을 사용합니다
"""
