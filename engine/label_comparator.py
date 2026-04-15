"""포장지 ↔ 물품사양서 대조

포장지 OCR 결과(dict)와 물품사양서 ProductSpec을 대조하여
항목별 일치/불일치 리스트를 생성.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any

from .pdf_parser import ProductSpec


@dataclass
class CompareRow:
    field: str
    label_value: str
    spec_value: str
    status: str  # match / mismatch / label_missing / spec_missing
    icon: str


COMPARE_FIELDS = [
    ("제품명", "제품명"),
    ("식품유형", "식품유형"),
    ("내용량", "내용량"),
    ("알레르기물질", "알레르기물질"),
    ("보관방법", "보관방법"),
    ("품목보고번호", "품목보고번호"),
]


def compare(label: Dict[str, Any], spec: ProductSpec) -> List[CompareRow]:
    rows: List[CompareRow] = []
    for lkey, skey in COMPARE_FIELDS:
        lv = _norm(label.get(lkey, "") if isinstance(label, dict) else "")
        sv = _norm(getattr(spec, skey, "") or "")
        if not lv and not sv:
            continue
        if not lv:
            rows.append(CompareRow(lkey, "", sv, "label_missing", "⚠"))
        elif not sv:
            rows.append(CompareRow(lkey, lv, "", "spec_missing", "⚠"))
        elif lv == sv or lv in sv or sv in lv:
            rows.append(CompareRow(lkey, lv, sv, "match", "✅"))
        else:
            rows.append(CompareRow(lkey, lv, sv, "mismatch", "❌"))
    return rows


def _norm(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip().replace(" ", "").replace("\n", "")
