"""증빙서류 매칭 — 업로드된 파일들을 서류 유형별로 분류하고 검증

- PDF 합본(여러 서류가 하나의 PDF)도 지원: 페이지별 텍스트를 키워드로 분류
- 각 서류별 제품명 일치, 유효기간 등 검증
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import pdfplumber
import re
import os

from .checklist_engine import ChecklistItem
from .pdf_parser import ProductSpec


# ---------------------------------------------------------------------------
# 서류 유형 키워드 (분류용)
# ---------------------------------------------------------------------------

DOC_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("물품사양서",          ["물품사양서", "물품표시사항"]),
    ("사업자등록증",        ["사업자등록증", "등록번호"]),
    ("영업등록증 또는 공장등록증", ["영업등록증", "공장등록증", "식품제조가공업", "영업신고증"]),
    ("품목제조보고대장",     ["품목제조보고", "품목보고"]),
    ("HACCP인증서",        ["HACCP", "안전관리인증", "해썹"]),
    ("원산지증명서",        ["원산지증명", "원산지 증명"]),
    ("수매확인서",          ["수매확인", "수매내역"]),
    ("자가 시험성적서",      ["자가품질검사", "자가품질", "자가검사"]),
    ("시험성적서",          ["시험성적서", "검사성적서", "성적서"]),
    ("방사능 검사서",       ["방사능", "Cs-137", "Cs-134", "I-131", "세슘", "요오드"]),
    ("중금속 검사서",       ["중금속", "납", "카드뮴", "수은", "Pb", "Cd", "Hg"]),
    ("용기 및 포장지 시험성적서", ["용기", "포장지", "폴리에틸렌", "PE", "포장재"]),
    ("원가계산서",          ["원가계산", "원가산정"]),
    ("상수도 고지서",       ["상수도", "수도요금"]),
    ("지하수 수질검사서",    ["지하수", "수질검사"]),
    ("Non-GMO 확인서",     ["Non-GMO", "Non GMO", "비유전자변형", "IP인증", "IP Identity"]),
    ("벤조피렌 검사 결과보고서", ["벤조피렌", "benzopyrene"]),
    ("천일염 방사능 시험성적서", ["천일염"]),  # 방사능과 조합 필요
    ("인증서 및 잔류농약성적서", ["잔류농약", "친환경", "유기농", "무농약", "인증서"]),
]


@dataclass
class MatchedDoc:
    doc_type: str
    source_file: str
    page_range: Optional[Tuple[int, int]]  # (start, end) 1-based
    text_snippet: str
    product_name_found: Optional[str] = None
    expiry_date: Optional[str] = None
    notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 파일 → 페이지 텍스트 추출
# ---------------------------------------------------------------------------

def _extract_pages(path: str) -> List[str]:
    """PDF이면 페이지별 텍스트, 이미지면 빈 리스트(OCR은 별도)"""
    ext = os.path.splitext(path)[1].lower()
    if ext != ".pdf":
        return []
    pages = []
    try:
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                pages.append(p.extract_text() or "")
    except Exception:
        pass
    return pages


# ---------------------------------------------------------------------------
# 분류기
# ---------------------------------------------------------------------------

def classify_documents(file_paths: List[str]) -> List[MatchedDoc]:
    """
    업로드된 파일들을 서류 유형별로 분류.
    합본 PDF는 페이지 구간별로 여러 MatchedDoc을 반환할 수 있음.
    """
    results: List[MatchedDoc] = []
    for path in file_paths:
        pages = _extract_pages(path)
        if not pages:
            # 이미지/빈 PDF: 파일명으로만 추정
            fn = os.path.basename(path)
            doc_type = _guess_by_filename(fn)
            results.append(MatchedDoc(
                doc_type=doc_type or "미분류",
                source_file=fn,
                page_range=None,
                text_snippet=""
            ))
            continue

        # 페이지별 유형 판별 → 연속 페이지는 묶기
        page_types = [_classify_text(p) for p in pages]
        # 연속 구간으로 그룹핑
        i = 0
        while i < len(pages):
            t = page_types[i]
            j = i
            while j + 1 < len(pages) and page_types[j + 1] == t:
                j += 1
            if t:
                snippet = "\n".join(pages[i:j + 1])[:2000]
                md = MatchedDoc(
                    doc_type=t,
                    source_file=os.path.basename(path),
                    page_range=(i + 1, j + 1),
                    text_snippet=snippet,
                )
                _extract_metadata(md)
                results.append(md)
            i = j + 1
    return results


def _classify_text(text: str) -> Optional[str]:
    if not text:
        return None
    # 우선순위: 물품사양서는 맨 위
    # 천일염+방사능 조합 먼저 체크
    if ("천일염" in text and ("방사능" in text or "Cs-137" in text or "세슘" in text)):
        return "천일염 방사능 시험성적서"
    for doc_type, keywords in DOC_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return doc_type
    return None


def _guess_by_filename(fn: str) -> Optional[str]:
    for doc_type, keywords in DOC_KEYWORDS:
        for kw in keywords:
            if kw in fn:
                return doc_type
    return None


def _extract_metadata(md: MatchedDoc):
    text = md.text_snippet or ""
    # 제품명 추출 (시험성적서류에서 중요)
    m = re.search(r"(?:제\s*품\s*명|품\s*목\s*명|시\s*료\s*명)\s*[:：]?\s*([^\n]{2,40})", text)
    if m:
        md.product_name_found = m.group(1).strip()
    # 유효기간
    m2 = re.search(r"(?:유효기간|유효\s*기간|인증\s*유효기간)\s*[:：]?\s*([0-9]{4}[.\-/][0-9]{1,2}[.\-/][0-9]{1,2})", text)
    if m2:
        md.expiry_date = m2.group(1).strip()
    else:
        m3 = re.search(r"([0-9]{4}[.\-/][0-9]{1,2}[.\-/][0-9]{1,2})\s*(?:까지|~까지)", text)
        if m3:
            md.expiry_date = m3.group(1).strip()


# ---------------------------------------------------------------------------
# 검증: 제출된 서류가 기대 목록과 일치하는지 확인
# ---------------------------------------------------------------------------

def verify_documents(
    spec: ProductSpec,
    required_items: List[ChecklistItem],
    matched: List[MatchedDoc],
) -> List[ChecklistItem]:
    """
    required_items: checklist_engine이 만든 '필요서류' 리스트
    matched:       업로드/분류된 서류 리스트
    반환:          status가 submitted/missing/warning 으로 갱신된 새 리스트
    """
    submitted_types = {m.doc_type: m for m in matched}
    result: List[ChecklistItem] = []
    product_name = (spec.제품명 or "").strip()

    for item in required_items:
        title = item.title
        md = submitted_types.get(title)
        if md is None:
            # 제목 일부 일치 (예: "영업등록증 또는 공장등록증" ↔ "영업등록증")
            for k, v in submitted_types.items():
                if k and (k in title or title in k):
                    md = v
                    break
        new = ChecklistItem(
            category=item.category,
            status="missing",
            title=item.title,
            description=item.description,
            action=item.action,
            regulation_ref=item.regulation_ref,
            icon="❌",
        )
        if md:
            new.status = "submitted"
            new.icon = "✅"
            notes = []
            # 제품명 일치 검증 (자가품질/시험성적서류)
            if md.product_name_found and product_name:
                if product_name not in md.product_name_found and md.product_name_found not in product_name:
                    new.status = "warning"
                    new.icon = "⚠"
                    notes.append(
                        f"검사서 제품명이 '{md.product_name_found}'로 되어 있습니다. "
                        f"현재 제품명 '{product_name}'과 불일치 — 재발급이 필요합니다."
                    )
            # 유효기간 임박
            if md.expiry_date:
                notes.append(f"유효기간: {md.expiry_date}")
                if _is_soon(md.expiry_date):
                    new.status = "warning"
                    new.icon = "⚠"
                    notes.append("⚠ 유효기간이 3개월 이내 만료됩니다. 갱신 여부를 확인하세요.")
            if notes:
                new.description = (new.description + "\n" + "\n".join(notes)).strip()
        result.append(new)
    return result


def _is_soon(date_str: str) -> bool:
    from datetime import datetime, timedelta
    try:
        s = date_str.replace("-", ".").replace("/", ".")
        dt = datetime.strptime(s, "%Y.%m.%d")
        return dt - datetime.now() < timedelta(days=90)
    except Exception:
        return False
