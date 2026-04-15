"""물품사양서 PDF 파서

우리농 물품사양서 PDF에서 제품 기본정보와 원재료 정보를 추출합니다.
- 1페이지: 물품표시사항 (4열 레이아웃) + 원재료 테이블
- 2페이지: 물품의 특징, 제조공정 등

AI 분석 엔진(ai_analyzer.py)에서는 extract_text_from_pdf()를 사용합니다.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
import pdfplumber
import re


# ---- 표시사항 key → 정규화 필드명 매핑 ----
FIELD_MAP = {
    "1.제품명": "제품명",
    "제품명": "제품명",
    "2.식품의유형": "식품유형",
    "식품의유형": "식품유형",
    "식품유형": "식품유형",
    "3.제조원": "제조원",
    "제조원": "제조원",
    "4.판매원": "판매원",
    "판매원": "판매원",
    "5.소비기한": "소비기한",
    "소비기한": "소비기한",
    "6.소비기한표시": "소비기한표시",
    "7.내용량": "내용량",
    "내용량": "내용량",
    "8.원재료및함량": "원재료표기",
    "9.알레르기물질": "알레르기물질",
    "알레르기물질": "알레르기물질",
    "10.용기(포장)재질": "용기포장재질",
    "11.품목보고번호": "품목보고번호",
    "12.소비자상담실": "소비자상담실",
    "13.바코드": "바코드",
    "14.보관방법": "보관방법",
    "보관방법": "보관방법",
    "15.반품및교환": "반품교환",
    "16.영양성분표시": "영양성분표시",
    "17.생산관리": "생산관리",
    "생산관리": "생산관리",
    "18.업체담당자": "업체담당자",
    "19.사용용수": "사용용수",
    "20.설비위생": "설비위생",
    "설비위생": "설비위생",
}


@dataclass
class Ingredient:
    name: str
    ratio: str = ""          # 배합비 (문자열 — 빈 값 허용)
    source: str = ""         # 제조/구입처
    origin: str = ""         # 원산지/재배방식

    def as_dict(self):
        return asdict(self)


@dataclass
class ProductSpec:
    # --- 헤더 ---
    교구: str = ""
    생산자: str = ""
    회원구분: str = ""
    물품제안: str = ""
    공급가: str = ""
    예상회원가: str = ""

    # --- 표시사항 ---
    제품명: str = ""
    식품유형: str = ""
    제조원: str = ""
    제조원주소: str = ""
    판매원: str = ""
    판매원주소: str = ""
    소비기한: str = ""
    소비기한표시: str = ""
    내용량: str = ""
    원재료표기: str = ""
    알레르기물질: str = ""
    용기포장재질: str = ""
    품목보고번호: str = ""
    소비자상담실: str = ""
    바코드: str = ""
    보관방법: str = ""
    반품교환: str = ""
    영양성분표시: str = ""
    생산관리: str = ""
    업체담당자: str = ""
    사용용수: str = ""
    설비위생: str = ""

    # --- 원재료 ---
    ingredients: List[Ingredient] = field(default_factory=list)

    # --- 기타 ---
    물품특징: str = ""
    제조공정: str = ""
    작성일시: str = ""
    raw_text: str = ""

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ingredients"] = [i for i in d["ingredients"]]
        return d


# =========================================================================
# 파싱 로직
# =========================================================================

def parse(pdf_path: str) -> ProductSpec:
    spec = ProductSpec()
    with pdfplumber.open(pdf_path) as pdf:
        all_text = []
        for pi, page in enumerate(pdf.pages):
            txt = page.extract_text() or ""
            all_text.append(txt)
            tables = page.extract_tables() or []
            if pi == 0:
                _parse_page1(spec, tables, txt)
            elif pi == 1:
                _parse_page2(spec, tables, txt)
        spec.raw_text = "\n".join(all_text)
    return spec


def _parse_page1(spec: ProductSpec, tables: list, text: str):
    ing_table = None
    for t in tables:
        if not t:
            continue
        first_row = [c for c in t[0] if c]
        first_text = " ".join(str(c) for c in first_row)

        # 헤더 테이블: 교구/생산자/회원구분
        if "교구" in first_text and "생산자" in first_text:
            _parse_header_table(spec, t)
            continue

        # 표시사항 테이블: "1. 물품표시사항" 타이틀 또는 "1.제품명" 포함
        joined = " ".join(str(c or "") for row in t for c in row)
        if "물품표시사항" in first_text or "제품명" in joined[:60]:
            _parse_display_table(spec, t)
            continue

        # 원재료 테이블
        if "원재료명" in joined and ("배합비" in joined or "배합" in joined):
            ing_table = t
            continue

    if ing_table:
        _parse_ingredient_table(spec, ing_table)


def _parse_header_table(spec: ProductSpec, table: list):
    """헤더 테이블: 1행 = 컬럼명, 2행 = 값, 3행 = 물품제안"""
    if len(table) < 2:
        return
    headers = [str(c or "").strip() for c in table[0]]
    values = [str(c or "").strip() for c in table[1]] if len(table) > 1 else []
    for h, v in zip(headers, values):
        if "교구" in h:
            spec.교구 = v
        elif "생산자" in h:
            spec.생산자 = v
        elif "회원구분" in h:
            spec.회원구분 = v
        elif "공급가" in h:
            spec.공급가 = v
        elif "예상회원가" in h:
            spec.예상회원가 = v
    for row in table[2:]:
        if not row:
            continue
        first = str(row[0] or "").strip()
        if "물품제안" in first:
            # 나머지 칸 중 비어있지 않은 값
            rest = [str(c or "").strip() for c in row[1:] if c]
            if rest:
                spec.물품제안 = rest[0]


def _parse_display_table(spec: ProductSpec, table: list):
    """
    표시사항 4열 테이블: [key, val, key, val]
    주소 연속행은 [None, 값, None, 값] 또는 None이 한쪽만 있을 수 있음.
    """
    last_left_idx = None   # 마지막 왼쪽 key의 필드명 (주소 연속 처리)
    last_right_idx = None  # 마지막 오른쪽 key의 필드명

    for row in table:
        if not row or all(c in (None, "") for c in row):
            continue
        cells = list(row) + [None] * (4 - len(row))
        k1, v1, k2, v2 = (cells[0], cells[1], cells[2], cells[3])

        k1s = (str(k1) if k1 else "").strip()
        v1s = (str(v1) if v1 else "").strip()
        k2s = (str(k2) if k2 else "").strip()
        v2s = (str(v2) if v2 else "").strip()

        # 타이틀 행("1. 물품표시사항") 스킵
        if k1s and ("물품표시사항" in k1s) and not v1s:
            continue

        # 왼쪽
        if k1s:
            field_name = FIELD_MAP.get(k1s) or FIELD_MAP.get(k1s.replace(" ", ""))
            if field_name:
                setattr(spec, field_name, _clean(v1s))
                last_left_idx = field_name
            else:
                last_left_idx = None
        else:
            # key 없음 = 주소 연속
            if last_left_idx in ("제조원", "판매원") and v1s:
                addr_field = last_left_idx + "주소"
                setattr(spec, addr_field, _clean(v1s))

        # 오른쪽
        if k2s:
            field_name = FIELD_MAP.get(k2s) or FIELD_MAP.get(k2s.replace(" ", ""))
            if field_name:
                setattr(spec, field_name, _clean(v2s))
                last_right_idx = field_name
            else:
                last_right_idx = None
        else:
            if last_right_idx in ("제조원", "판매원") and v2s:
                addr_field = last_right_idx + "주소"
                setattr(spec, addr_field, _clean(v2s))


def _parse_ingredient_table(spec: ProductSpec, table: list):
    """
    원재료 테이블:
      row 0: ['2. 원재료명 및 함량', None, ...]  (타이틀)
      row 1: ['원재료명', '배합비(%)', '제조/구입처', '원산지/재배방식']
      row 2+: 데이터
    """
    start_idx = 0
    for i, row in enumerate(table):
        if not row:
            continue
        first = str(row[0] or "")
        if "원재료명" in first and "배합" in " ".join(str(c or "") for c in row):
            start_idx = i + 1
            break
    for row in table[start_idx:]:
        if not row or not row[0]:
            continue
        name = _clean(str(row[0]))
        if not name or "원재료명" in name:
            continue
        ratio = _clean(str(row[1])) if len(row) > 1 and row[1] else ""
        source = _clean(str(row[2])) if len(row) > 2 and row[2] else ""
        origin = _clean(str(row[3])) if len(row) > 3 and row[3] else ""
        spec.ingredients.append(Ingredient(name=name, ratio=ratio, source=source, origin=origin))


def _parse_page2(spec: ProductSpec, tables: list, text: str):
    # 물품의 특징, 제조공정, 작성일시 추출
    feat = re.search(r"3\.\s*물품의\s*특징\s*(.*?)(?=4\.\s*제조공정|$)", text, re.S)
    if feat:
        spec.물품특징 = feat.group(1).strip()
    proc = re.search(r"4\.\s*제조공정\s*(.*?)(?=5\.\s*사양확인|$)", text, re.S)
    if proc:
        spec.제조공정 = proc.group(1).strip()
    date = re.search(r"작성일시\s*[:：]?\s*([0-9.\-/ ]+)", text)
    if date:
        spec.작성일시 = date.group(1).strip()


def _clean(s: str) -> str:
    if s is None:
        return ""
    return str(s).replace("\n", " ").strip()


# ─────────────────────────────────────────────────
# AI 분석 엔진용 전체 텍스트 추출
# ─────────────────────────────────────────────────

def extract_text_from_pdf(pdf_path: str) -> str:
    """PDF 전 페이지 텍스트를 하나의 문자열로 추출 (AI 분석 엔진용)."""
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(f"[PAGE {i+1}]\n{text}")
    except Exception as e:
        return f"[PDF 텍스트 추출 실패: {e}]"
    return "\n\n".join(pages)
