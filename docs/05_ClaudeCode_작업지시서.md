# 우리농 신규물품 심의 보조 웹앱 — Claude Code 작업 지시서

## 프로젝트 개요

가톨릭농민회/우리농촌살리기운동본부의 신규 가공식품 심의를 보조하는 로컬 웹 애플리케이션을 개발합니다. 물품사양서(PDF)와 증빙서류(PDF/JPG)를 업로드하면 우리농 가공식품 생산규정에 따라 자동 분석하고, 판정 결과를 엑셀 또는 PDF로 출력합니다.

**이 프로젝트는 두 단계로 구성됩니다:**
- **Phase 1**: 규정 데이터 엑셀 파일 생성 + PDF 파싱 모듈 + 규칙 기반 판정 엔진
- **Phase 2**: Flask 웹 UI + 보고서 출력 (엑셀/PDF)

**기술 스택**: Python 3.10+, Flask, pdfplumber, openpyxl, reportlab, Jinja2

---

## 디렉토리 구조

```
woori-review-app/
├── app.py                    # Flask 메인 앱
├── config.py                 # 설정 (포트, 경로 등)
├── requirements.txt          # 의존성
├── README.md                 # 사용법 안내
│
├── data/                     # 규정 데이터 (토니가 직접 수정 가능)
│   ├── 제출서류_매핑.xlsx
│   ├── 원재료_기준.xlsx
│   ├── 첨가물_허용목록.xlsx
│   ├── GMO_목록.xlsx
│   ├── 수입허용원료.xlsx
│   ├── 표시사항_체크.xlsx
│   └── 분과_매핑.xlsx
│
├── engine/                   # 핵심 로직
│   ├── __init__.py
│   ├── pdf_parser.py         # 물품사양서 PDF 파싱
│   ├── doc_classifier.py     # 증빙서류 분류
│   ├── rule_checker.py       # 규정 대조 판정 엔진
│   ├── report_generator.py   # 보고서 생성 (엑셀/PDF)
│   └── label_checker.py      # 라벨 대조 (향후 확장)
│
├── templates/                # HTML 템플릿
│   └── index.html            # 단일 페이지 UI
│
├── static/                   # CSS/JS
│   └── style.css
│
├── uploads/                  # 업로드된 파일 임시 저장
└── outputs/                  # 생성된 보고서 저장
```

---

## Phase 1: 규정 데이터 엑셀 파일

### 1-1. 제출서류_매핑.xlsx

**시트명**: 제출서류

| 열 | 내용 | 예시 |
|---|---|---|
| A: 번호 | 일련번호 | 1 |
| B: 서류명 | 서류 이름 | 물품사양서 |
| C: 필수여부 | 필수 / 조건부 | 필수 |
| D: 조건_필드 | 조건 판단에 사용할 물품사양서 필드 | (없음=항상필수) |
| E: 조건_값 | 해당 필드가 이 값일 때 필요 | (없음) |
| F: 조건_설명 | 사람이 읽을 수 있는 설명 | 모든 물품 |

**데이터** (19행):
```
1, 물품사양서, 필수, , , 모든 물품
2, 사업자등록증, 필수, , , 모든 물품
3, 영업등록증 또는 공장등록증, 필수, , , 모든 물품
4, 품목제조보고대장, 필수, , , 모든 물품
5, 원산지증명서, 필수, , , 모든 물품 (원재료별)
6, 인증서 및 잔류농약성적서, 필수, , , 모든 물품
7, 시험성적서, 필수, , , 모든 물품
8, 지하수 수질검사서, 조건부, 사용용수, 지하수, 사용용수가 지하수인 경우
9, 상수도 고지서, 조건부, 사용용수, 상수도, 사용용수가 상수도인 경우
10, 자가 시험성적서, 필수, , , 모든 물품
11, 용기 및 포장지 시험성적서, 필수, , , 모든 물품
12, 수매확인서, 조건부, 원료유형, 수산물, 수산물 원료 사용 시
13, 원산지증명서(수산물), 조건부, 원료유형, 수산물, 수산물 원료 사용 시
14, 중금속 검사서, 조건부, 원료유형, 수산물, 수산물 원료 사용 시
15, 방사능 검사서, 조건부, 원료유형, 수산물, 수산물 원료 사용 시
16, 원가계산서, 필수, , , 모든 물품
17, 벤조피렌 검사 결과보고서, 조건부, 원료유형, 기름류, 기름류(참기름 들기름 등)
18, Non-GMO 확인서, 조건부, 원료유형, GMO위험, 두류 옥수수 원료 사용 시
19, 천일염 방사능 시험성적서, 조건부, 소금종류, 천일염, 소금 원료가 천일염인 경우
```

### 1-2. 원재료_기준.xlsx

**시트1: 원재료구분별기준** (운영규정 제8호)

| 열 | 내용 |
|---|---|
| A: 원재료구분 | 주곡원료, 잡곡원료, 과일견과원료, 채소원료, 축산물원료, 수산물원료, 당류, 유지, 소금, 기타원료 |
| B: 기본기준 | "무농약 이상 유기농 권장", "국산 이상" 등 |
| C: 권장사항 | 추가 권장사항 |
| D: 금지사항 | 해당 구분의 금지 원료 |

**데이터**:
```
주곡원료, 무농약 이상 유기농 권장, , 
잡곡원료, 국산 이상, , 
과일견과원료, 국산 이상 가농인증 및 친환경인증 우선 수입유기농 가능, , 
채소원료, 국산 이상, 무농약 이상 채소 권장, 
축산물원료, 무항생제 유정란 이상 권장, 국산 난백액 일부 허용, 
수산물원료, 국산 이상, 어묵:국산어육권장 수입연육허용 / 황태:러시아산 국내가공허용, 
당류, 백설탕 이상, 유기농설탕 프락토올리고당 조청 천연꿀 권장, GMO원료 물엿 금지 / 합성감미료 금지
유지, Non-GMO 기름만 허용, 올리브유 현미유 포도씨유 해바라기씨유 팜유, 경화유(마가린 쇼트닝 팜경화유 가공버터) 금지 / 수입콩기름 수입옥수수기름 금지
소금, 국산정제염 이상, 천일염 구운소금 자염 죽염 권장, 
기타원료, , , 
```

**시트2: 유지_허용목록**

| 열 | 내용 |
|---|---|
| A: 유지명 | 현미유, 포도씨유, 해바라기씨유, 올리브유, 팜유 |
| B: GMO여부 | Non-GMO |
| C: 비고 | |

**시트3: 유지_금지목록**

| 열 | 내용 |
|---|---|
| A: 유지명 | 콩기름, 옥수수기름, 카놀라유, 면실유, 마가린, 쇼트닝, 팜경화유, 가공버터 |
| B: 금지사유 | GMO유래 또는 경화유 |

**시트4: 당류_허용목록**

| A: 당류명 | B: 등급 | C: 비고 |
|---|---|---|
| 백설탕 | 기본 | |
| 유기농설탕 | 권장 | |
| 프락토올리고당 | 허용 | 원당100% 비GMO만 |
| 이소말토올리고당 | 조건부 | 쌀원료만 허용 |
| 자일로올리고당 | 허용 | 나무/설탕원료 |
| 국산조청 | 권장 | |
| 천연꿀 | 권장 | |
| 사양꿀 | 허용 | |
| 스테비오사이드 | 허용 | 감미료(스테비아 추출) |

**시트5: 당류_금지목록**

| A: 당류명 | B: 금지사유 |
|---|---|
| 수입옥수수전분물엿 | GMO원료 |
| 이소말토올리고당(수입옥수수원료) | GMO원료 |
| 갈락토올리고당(수입우유/설탕) | GMO원료 |
| 합성감미료 | 합성첨가물 |

### 1-3. GMO_목록.xlsx

**시트1: GMO_농산물**

| A: GM농산물 | B: 주요파생식품 | C: 확인키워드 |
|---|---|---|
| GM대두 | 콩기름 콩깻묵 탈지대두 대두단백 라면스프 간장 된장 고추장 두부 콩나물 두유 | 대두,콩,soy,탈지대두,대두단백 |
| GM옥수수 | 올리고당 물엿 포도당 액상과당 아스파탐 옥수수유 팝콘 시리얼 | 옥수수,corn,옥수수전분,옥수수그릿츠,물엿,올리고당,포도당,액상과당 |
| GM면화 | 면실유 | 면실유,cottonseed |
| GM감자 | 녹말가루 당면 감자튀김 | 감자,potato |
| GM카놀라 | 카놀라유 유채유 | 카놀라,canola,유채 |

**시트2: GMO_확인필요원료** (물품사양서에서 발견 시 자동 플래그)

| A: 키워드 | B: 확인사항 |
|---|---|
| 옥수수 | Non-GMO 확인서 필요 |
| 대두 | Non-GMO 확인서 필요 |
| 콩 | Non-GMO 확인서 필요 |
| 변성전분 | Non-GMO 원료 확인 필요 |
| 효모 | Non-GMO 배지 기반 확인 필요 |
| 효모추출물 | Non-GMO 배지 기반 확인 필요 |
| 발효주정 | Non-GMO 원료(타피오카 등) 확인 필요 |
| 물엿 | GMO 옥수수전분 유래 여부 확인 |
| 올리고당 | 원당100% 프락토올리고당인지 확인 |
| 레시틴 | Non-GMO 대두 유래 확인 |

### 1-4. 수입허용원료.xlsx

**시트1: 향신료** (18종)

| A: 번호 | B: 원료명 | C: 원산지 | D: 비고 |
|---|---|---|---|
| 1~18 | 올스파이스, 바질, 월계수잎, 계피, 코리안더, 정향, 커리, 큐민, 샐러드시드, 딜, 오레가노, 박하/페퍼민트, 겨자, 파슬리, 후추, 로즈마리, 샤프론, 바닐라 | 각각의 원산지 | |

**시트2: 약재** (4종)

| A: 원료명 | B: 원산지 |
|---|---|
| 육계 | 베트남 |
| 산조인 | |
| 감초 | |
| 계피 | |

**시트3: 기름류** (5종)

| A: 원료명 | B: GMO여부 |
|---|---|
| 현미유 | Non-GMO |
| 포도씨유 | Non-GMO |
| 해바라기씨유 | Non-GMO |
| 올리브유 | Non-GMO |
| 팜유 | Non-GMO |

### 1-5. 표시사항_체크.xlsx

**시트1: 필수표시항목** (물품사양서 20개 항목)

| A: 번호 | B: 항목명 | C: 필수여부 | D: 공란허용 | E: 비고 |
|---|---|---|---|---|
| 1 | 제품명 | 필수 | 불가 | |
| 2 | 식품의유형 | 필수 | 불가 | |
| 3 | 제조원 | 필수 | 불가 | 명칭+주소 |
| 4 | 판매원 | 필수 | 불가 | 명칭+주소 |
| 5 | 소비기한 | 필수 | 불가 | |
| 6 | 소비기한표시 | 필수 | 불가 | "제품 별도 표기" 허용 |
| 7 | 내용량 | 필수 | 불가 | |
| 8 | 원재료및함량 | 필수 | 불가 | "하단 참조" 허용 |
| 9 | 알레르기물질 | 필수 | 불가 | "해당사항 없음" 허용 |
| 10 | 용기포장재질 | 필수 | 불가 | |
| 11 | 품목보고번호 | 필수 | 불가 | |
| 12 | 소비자상담실 | 필수 | 불가 | |
| 13 | 바코드 | 필수 | 불가 | |
| 14 | 보관방법 | 필수 | 불가 | |
| 15 | 반품및교환 | 필수 | 불가 | |
| 16 | 영양성분표시 | 조건부 | 조건부 | 표시대상식품인 경우 필수 |
| 17 | 생산관리 | 필수 | 불가 | "가톨릭농민회" 또는 제조원 |
| 18 | 업체담당자 | 필수 | 불가 | |
| 19 | 사용용수 | 필수 | 불가 | 상수도/지하수 |
| 20 | 설비위생 | 필수 | 불가 | |

**시트2: 영양성분표시대상** (식품유형 목록)

| A: 식품유형키워드 | B: 의무여부 |
|---|---|
| 과자 | 의무 |
| 캔디 | 의무 |
| 빙과 | 의무 |
| 빵 | 의무 |
| 만두 | 의무 |
| 초콜릿 | 의무 |
| 잼 | 의무 |
| 식용유지 | 의무 |
| 면류 | 의무 |
| 음료 | 의무 |
| 어육소시지 | 의무 |
| 즉석섭취 | 의무 |
| 김밥 | 의무 |
| 햄버거 | 의무 |
| 샌드위치 | 의무 |
| 레토르트 | 의무 |

**시트3: 알레르기유발물질** (21종)

| A: 물질명 |
|---|
| 메밀, 밀, 대두, 호두, 땅콩, 복숭아, 토마토, 돼지고기, 난류, 우유, 닭고기, 쇠고기, 새우, 고등어, 홍합, 전복, 굴, 조개류, 게, 오징어, 아황산류 |

### 1-6. 첨가물_허용목록.xlsx

**시트1: 천연첨가물** (운영규정 제3호) — 14행

| A: 용도 | B: 첨가물명 | C: 사용품목 | D: 첨가이유 | E: 비고 |
|---|---|---|---|---|
| (운영규정 제3호 테이블 그대로 입력) |

**시트2: 유기가공인증허용첨가물** (운영규정 제4호) — 52행

| A: 번호 | B: 명칭한 | C: 명칭영 | D: 용도 | E: 허용범위 |
|---|---|---|---|---|
| (운영규정 제4호 테이블 그대로 입력) |

### 1-7. 분과_매핑.xlsx

**시트1: 식품유형_분과매핑** (운영규정 제6호)

| A: 분과구분 | B: 식품유형 | C: 식품유형세분 | D: HACCP의무 | E: 영양성분표시 | F: 자가품질검사주기 |
|---|---|---|---|---|---|
| (운영규정 제6호 테이블 전체 입력) |

---

## Phase 1: 핵심 로직 모듈

### engine/pdf_parser.py

**목적**: 물품사양서 PDF에서 구조화된 데이터 추출

**추출 대상 필드**:
```python
class ProductSpec:
    # 기본정보
    product_name: str          # 제품명
    food_type: str             # 식품의유형
    diocese: str               # 교구
    producer: str              # 생산자
    member_type: str           # 회원구분 (정/비/협)
    member_ingredient: str     # 회원원재료사용 (O/X)
    manufacturer: str          # 제조원
    manufacturer_addr: str     # 제조원 주소
    seller: str                # 판매원
    seller_addr: str           # 판매원 주소
    shelf_life: str            # 소비기한
    net_weight: str            # 내용량
    storage_method: str        # 보관방법
    water_source: str          # 사용용수
    packaging_material: str    # 용기(포장)재질
    allergens: str             # 알레르기물질
    product_report_no: str     # 품목보고번호
    barcode: str               # 바코드
    hygiene: str               # 설비위생
    production_mgmt: str       # 생산관리
    supply_price: str          # 공급가
    member_price: str          # 예상회원가
    
    # 원재료 테이블
    ingredients: List[Ingredient]  # 원재료 목록
    
    # 물품 특징, 제조공정
    product_features: str
    manufacturing_process: str

class Ingredient:
    name: str           # 원재료명
    ratio: str          # 배합비(%) — 빈 문자열이면 미기재
    supplier: str       # 제조/구입처
    origin: str         # 원산지/재배방식
```

**파싱 전략**:
1. pdfplumber로 PDF의 각 페이지에서 테이블과 텍스트 추출
2. 1페이지: 상단 표 (교구, 생산자, 회원구분 등) + 물품표시사항 테이블 (20개 항목) + 원재료 테이블
3. 2페이지: 물품의 특징, 제조공정
4. 테이블 추출 실패 시 텍스트 기반 파싱으로 폴백

**주의사항**:
- 물품사양서 양식이 2018년/2026년 등 버전별로 다를 수 있음 → 유연한 파싱 필요
- 배합비가 비어있는 경우를 정확히 탐지해야 함
- "하단 참조", "제품 별도 표기", "해당사항 없음" 등의 특수 기재를 인식해야 함

### engine/rule_checker.py

**목적**: 추출된 물품사양서 데이터를 규정 엑셀과 대조하여 판정

**판정 로직 (의사코드)**:

```python
def check_product(spec: ProductSpec, regulations: RegulationData) -> ReviewResult:
    issues = []
    warnings = []
    
    # 1. 물품사양서 기재 완전성 점검
    for field in regulations.required_fields:
        if is_blank(spec, field):
            issues.append(Issue("미기재", field.name, "재검토"))
    
    # 2. 원재료 배합비 점검
    total_ratio = 0
    has_blank_ratio = False
    for ing in spec.ingredients:
        if ing.ratio == "":
            has_blank_ratio = True
            issues.append(Issue("배합비 미기재", ing.name, "재검토"))
        else:
            total_ratio += float(ing.ratio)
    
    if not has_blank_ratio and abs(total_ratio - 100.0) > 0.5:
        issues.append(Issue("배합비 합계 불일치", f"{total_ratio}%", "재검토"))
    
    # 3. 원재료별 규정 대조
    for ing in spec.ingredients:
        # 3-1. 원산지 확인
        if is_imported(ing.origin):
            if not in_allowed_imports(ing.name, regulations.allowed_imports):
                warnings.append(Warning("수입원료 허용여부 확인", ing.name, 
                    "운영규정 제1호 허용 목록에 미포함"))
        
        # 3-2. GMO 위험 원료
        for keyword in regulations.gmo_keywords:
            if keyword in ing.name:
                warnings.append(Warning("GMO 확인 필요", ing.name,
                    f"운영규정 제2호: {keyword} 관련 GMO 확인"))
        
        # 3-3. 유지류 점검
        if is_oil(ing.name):
            if in_banned_oils(ing.name, regulations.banned_oils):
                issues.append(Issue("금지 유지류", ing.name, "반려",
                    "취급기준(원부재료): 경화유 사용 금지"))
        
        # 3-4. 당류 점검
        if is_sugar(ing.name):
            if in_banned_sugars(ing.name, regulations.banned_sugars):
                issues.append(Issue("금지 당류", ing.name, "반려"))
        
        # 3-5. 소금 점검
        if is_salt(ing.name):
            if ing.name == "소금":  # 종류 미특정
                warnings.append(Warning("소금 종류 미특정", ing.name,
                    "천일염/정제염/구운소금 등 확인 필요"))
            if "천일염" in ing.name:
                # 천일염 방사능 성적서 필요 플래그
                pass  # 증빙서류 체크에서 처리
        
        # 3-6. 첨가물 점검
        if is_additive(ing.name):
            if not in_allowed_additives(ing.name, regulations):
                warnings.append(Warning("허용 첨가물 목록 확인", ing.name,
                    "운영규정 제3호/제4호 허용 목록 대조 필요"))
        
        # 3-7. 원재료 분류 경계 사례 탐지 ★ 중요
        boundary = check_ingredient_classification(ing, spec.product_name)
        if boundary:
            warnings.append(Warning("원재료 분류 경계 사례", ing.name,
                boundary.description))
    
    # 4. 영양성분 표시 의무 확인
    if is_nutrition_label_required(spec.food_type, regulations):
        if spec.nutrition_label in ["", "제품 별도 표기"]:
            warnings.append(Warning("영양성분표시 확인", 
                "영양성분 표시 의무 대상 — 실제 표시 여부 확인"))
    
    # 5. 판정 산출
    verdict = determine_verdict(issues, warnings)
    
    return ReviewResult(spec, issues, warnings, verdict)


def check_ingredient_classification(ing: Ingredient, product_name: str) -> BoundaryCase:
    """원재료 분류 경계 사례 탐지 (바나나농축분말 케이스 등)"""
    
    # 농산물 가공 형태 키워드
    processed_forms = ["농축분말", "퓨레", "착즙액", "추출물", "농축액", "분말", "파우더", "페이스트"]
    
    # 제품명에 원료명이 포함되어 있는지
    name_in_product = any(part in product_name for part in ing.name.split())
    
    # 가공 형태인지
    is_processed = any(form in ing.name for form in processed_forms)
    
    # 수입원료인지
    is_imported = ing.origin not in ["국산", "국내산", ""]
    
    if is_processed and (name_in_product or is_imported):
        return BoundaryCase(
            ingredient=ing.name,
            description=f"'{ing.name}'은(는) 농산물 가공품(원부재료)으로 볼 것인지, "
                       f"첨가물/향신료로 볼 것인지에 따라 수입 허용 여부와 유기인증 "
                       f"요구 수준이 달라집니다. "
                       f"{'제품명에 해당 원료명이 포함되어 있어 주요 핵심원료로 간주될 수 있습니다. ' if name_in_product else ''}"
                       f"위원회 논의를 통해 분류를 확정하시기 바랍니다. "
                       f"(지식베이스 제17조 참조)"
        )
    
    return None


def determine_verdict(issues, warnings) -> str:
    """판정 우선순위: 반려 > 재검토 > 서류보완 > 승인"""
    severities = [i.severity for i in issues]
    if "반려" in severities:
        return "반려"
    if "재검토" in severities:
        return "재검토"
    if "서류보완" in severities:
        return "서류보완"
    return "승인"
```

### engine/doc_classifier.py

**목적**: 증빙서류 PDF/JPG에서 서류 종류를 1차 분류

**분류 전략**:
```python
DOCUMENT_KEYWORDS = {
    "사업자등록증": ["사업자등록증", "사업자등록번호", "등록번호"],
    "영업등록증": ["영업등록증", "영업신고증", "공장등록증"],
    "품목제조보고대장": ["품목제조보고", "품목제조신고"],
    "HACCP인증서": ["HACCP", "식품안전관리인증", "해썹"],
    "원산지증명서": ["원산지", "원산지증명"],
    "시험성적서": ["시험성적서", "시험검사", "검사성적서"],
    "방사능검사서": ["방사능", "방사선", "I-131", "Cs-134", "Cs-137"],
    "수질검사서": ["수질검사", "수질"],
    "자가품질검사서": ["자가품질", "자가검사", "위탁검사"],
    "포장지시험성적서": ["포장", "용기", "식품포장지", "PE", "Polyethylene"],
    "수매확인서": ["수매확인", "수매"],
    "중금속검사서": ["중금속", "납", "카드뮴", "수은"],
    "원가계산서": ["원가계산", "원가"],
    "Non-GMO확인서": ["Non-GMO", "비유전자변형", "IP인증"],
    "벤조피렌검사서": ["벤조피렌"],
    "천일염방사능성적서": ["천일염", "방사능"],
}
```

**주의**: 자가품질검사서의 경우, 해당 제품의 검사서인지 **제품명을 대조**해야 함 (가자미구이 사례에서 발견된 이슈).

### engine/report_generator.py

**목적**: 분석 결과를 엑셀 또는 PDF 보고서로 생성

**엑셀 출력 구조** (openpyxl):
- 시트1 "기본정보": 제품 기본정보 테이블
- 시트2 "원재료분석": 원재료별 적합성 분석 테이블
- 시트3 "기재점검": 미기재/오류 항목 목록
- 시트4 "증빙서류": 필요서류 체크리스트 + 제출현황 (기능2)
- 시트5 "판정결과": 최종 판정 + 사유 + 보완사항

---

## Phase 2: Flask 웹 UI

### templates/index.html

**단일 페이지, 2개 탭 구성**:

**탭 1: 심의 준비 (기능 1)**
- 물품사양서 PDF 업로드 (드래그앤드롭 또는 파일 선택)
- [선택] 제품 라벨 사진 업로드 (JPG/PNG)
- "분석 시작" 버튼
- 결과 표시 영역 (원재료 분석, 기재 점검, 필요 서류 등)
- "엑셀 다운로드" / "PDF 다운로드" 버튼

**탭 2: 심의 판정 (기능 2)**
- 물품사양서 PDF 업로드
- 증빙서류 PDF/JPG 복수 업로드
- [선택] 제품 라벨 사진 업로드
- "분석 및 판정" 버튼
- 결과 표시 영역 (기능 1 결과 + 증빙서류 매칭 + 판정)
- "엑셀 다운로드" / "PDF 다운로드" 버튼

**설정 탭 (사이드바 또는 별도 탭)**:
- 규정 데이터 엑셀 파일 업로드/교체
- 현재 적용 중인 규정 파일 목록 표시

### 디자인 방향
- 깔끔하고 실무적인 UI (그린 계열 — 가톨릭농민회 CI 참조)
- 모바일 반응형 (태블릿에서도 사용 가능)
- 한글 폰트 적용 (Noto Sans KR)

---

## 실행 방법

```bash
# 설치
cd woori-review-app
pip install -r requirements.txt

# 실행
python app.py

# 브라우저에서 접속
http://localhost:5000
```

---

## 테스트 데이터

다음 2개 물품사양서로 테스트합니다:

1. **우리밀 바나나송송** — 복잡한 케이스 (GMO 위험, 수입원료, 배합비 미기재, 원재료 분류 경계 사례)
   - 기대 판정: 재검토

2. **아라찬 가자미구이** — 증빙서류 포함 케이스 (서류 누락, 다른 제품 검사서 혼입)
   - 기대 판정: 서류 보완

---

## 개발 우선순위

1. **먼저**: 규정 데이터 엑셀 7개 파일 생성
2. **다음**: pdf_parser.py + rule_checker.py (핵심 로직)
3. **다음**: doc_classifier.py (증빙서류 분류)
4. **다음**: report_generator.py (엑셀 출력)
5. **다음**: Flask app.py + index.html (웹 UI)
6. **다음**: 테스트 데이터로 통합 검증
7. **이후**: Phase 3 (클라우드 배포)
8. **이후**: Phase 4 (구글 드라이브 연동)

---

## Phase 3: 클라우드 배포 (로컬 검증 완료 후)

### 목표
누구나 웹 브라우저에서 URL로 접속하여 물품사양서/증빙서류를 업로드하고, 분석 결과를 보고 다운로드할 수 있어야 합니다. 별도의 프로그램 설치 없이 사용 가능해야 합니다.

### 배포 플랫폼 선택지

| 플랫폼 | 무료 티어 | 장점 | 단점 |
|---|---|---|---|
| **Render** | 월 750시간 (충분) | 설정 간단, GitHub 연동, HTTPS 자동 | 무료 티어는 15분 미사용 시 슬립 (첫 접속 시 30초 대기) |
| **Railway** | 월 $5 크레딧 | 빠른 배포, 환경변수 관리 편리 | 무료 크레딧 소진 시 유료 |
| **PythonAnywhere** | 무료 | Python 특화, 안정적 | Flask 외 프레임워크 제한, 도메인 제한 |
| **Fly.io** | 소규모 무료 | 글로벌 엣지, Docker 기반 | 설정 복잡도 중간 |

**권장**: Render (무료, 설정 간편, Flask 호환 좋음)

### 배포 시 추가 파일

```
woori-review-app/
├── ... (기존 파일)
├── Procfile                  # Render/Heroku용 실행 명령
├── gunicorn_config.py        # 프로덕션 WSGI 서버 설정
└── runtime.txt               # Python 버전 지정
```

**Procfile**:
```
web: gunicorn app:app --config gunicorn_config.py
```

**requirements.txt에 추가**:
```
gunicorn
```

### 배포 시 고려사항

1. **파일 저장**: 클라우드 서버는 재시작 시 업로드 파일이 삭제됨 → 분석 결과는 즉시 다운로드하도록 안내. 영구 저장이 필요하면 Phase 4(구글 드라이브)로 해결.

2. **규정 엑셀 관리**: `data/` 폴더의 규정 엑셀 파일은 Git 저장소에 포함시켜 배포. 규정 변경 시 Git에 커밋하면 자동 재배포.

3. **보안**: 물품사양서, 증빙서류 등 내부 문서가 서버를 거치므로:
   - HTTPS 필수 (Render는 자동 제공)
   - 업로드 파일은 분석 완료 후 즉시 삭제
   - 필요 시 간단한 접속 비밀번호(환경변수) 설정

4. **동시 사용자**: 무료 티어로 5~10명 동시 접속 정도는 무리 없음. 생소실회의 참석자 수준.

### 배포 절차 (Render 기준)

```bash
# 1. GitHub에 프로젝트 푸시
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/[계정]/woori-review-app.git
git push -u origin main

# 2. Render 웹사이트에서
# - New > Web Service
# - GitHub 저장소 연결
# - Build Command: pip install -r requirements.txt
# - Start Command: gunicorn app:app
# - 무료 플랜 선택
# → 자동으로 URL 생성 (예: woori-review-app.onrender.com)
```

---

## Phase 4: 구글 드라이브 연동

### 목표
구글 드라이브에 물품별 폴더가 있고, 각 폴더에 물품사양서와 증빙서류가 업로드되어 있을 때, 웹앱에서 해당 폴더를 선택하면 파일을 자동으로 불러와 분석하고 결과를 산출합니다.

### 구글 드라이브 폴더 구조 (권장)

```
우리농 신규물품 심의/
├── 2026-04_바나나송송_우리밀/
│   ├── 물품사양서_우리밀바나나송송.pdf
│   ├── 사업자등록증.pdf
│   ├── 영업등록증.pdf
│   ├── 품목제조보고대장.pdf
│   └── ...
├── 2026-04_가자미구이_씨글로벌/
│   ├── 물품사양서_아라찬가자미구이.pdf
│   ├── HACCP인증서.pdf
│   └── ...
└── ...
```

**폴더 명명 규칙 권장**: `YYYY-MM_제품명_생산자` (정렬 편의)

### 기술 구현

**방법 A: Google Drive API (서비스 계정)** — 권장

```python
# engine/gdrive_connector.py

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GDriveConnector:
    def __init__(self, credentials_path: str):
        creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES)
        self.service = build('drive', 'v3', credentials=creds)
    
    def list_product_folders(self, parent_folder_id: str) -> list:
        """상위 폴더 내 물품별 하위 폴더 목록 조회"""
        results = self.service.files().list(
            q=f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
            fields="files(id, name, modifiedTime)"
        ).execute()
        return results.get('files', [])
    
    def list_files_in_folder(self, folder_id: str) -> list:
        """폴더 내 파일 목록 조회"""
        results = self.service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="files(id, name, mimeType, size)"
        ).execute()
        return results.get('files', [])
    
    def download_file(self, file_id: str, destination_path: str):
        """파일 다운로드"""
        request = self.service.files().get_media(fileId=file_id)
        with open(destination_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()
```

**설정 필요사항**:
1. Google Cloud Console에서 프로젝트 생성
2. Google Drive API 활성화
3. 서비스 계정 생성 → JSON 키 파일 다운로드
4. 구글 드라이브의 상위 폴더를 서비스 계정 이메일에 공유
5. JSON 키 파일을 앱의 `config/` 폴더에 저장 (Git에는 올리지 않음)

**방법 B: Google Picker API (사용자 인증)** — 대안

사용자가 웹앱에서 직접 구글 계정으로 로그인하여 드라이브 폴더를 선택하는 방식. 서비스 계정 설정 없이 사용 가능하나, OAuth 동의 화면 설정이 필요하고 사용자마다 로그인해야 함.

### 웹 UI 추가 요소 (Phase 4)

**탭 1, 탭 2에 추가**:
- 파일 업로드 영역 아래에 "구글 드라이브에서 불러오기" 버튼
- 클릭 시 물품별 폴더 목록 표시 (드롭다운 또는 모달)
- 폴더 선택 → 해당 폴더의 파일 자동 다운로드 → 분석 시작

**별도 탭 "드라이브 연동"**:
- 구글 드라이브 연결 상태 표시
- 상위 폴더 ID 설정
- 폴더 목록 새로고침

### requirements.txt 추가

```
google-auth
google-auth-oauthlib
google-api-python-client
```

### 구글 드라이브 연동 시 분석 결과 저장

분석 완료 후 결과 보고서(엑셀/PDF)를 해당 물품 폴더에 자동 업로드하는 옵션도 가능:

```python
def upload_report(self, folder_id: str, file_path: str, file_name: str):
    """분석 결과를 구글 드라이브 폴더에 업로드"""
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path)
    self.service.files().create(
        body=file_metadata, media_body=media
    ).execute()
```

이렇게 하면 물품 폴더에 물품사양서, 증빙서류, **심의 결과 보고서**가 한곳에 보관됨.

---

## 전체 로드맵 요약

| Phase | 내용 | 결과 |
|---|---|---|
| 1 | 규정 데이터 + 핵심 로직 | 로컬에서 CLI로 분석 가능 |
| 2 | Flask 웹 UI + 보고서 출력 | 로컬에서 브라우저로 사용 |
| 3 | 클라우드 배포 | 누구나 URL로 접속 사용 |
| 4 | 구글 드라이브 연동 | 드라이브 폴더에서 바로 분석 + 결과 저장 |

---

## 참조 파일

이 프로젝트의 판정 로직과 규정 구조는 다음 파일에서 검증되었습니다:
- `01_규정_지식베이스_v2.md` — 규정 전체 구조화 문서
- `02_시스템_프롬프트_v2.md` — 판정 로직과 분석 절차
- `03_분석결과_우리밀바나나송송.md` — 기능 1 검증 결과
- `04_판정결과_아라찬가자미구이.md` — 기능 2 검증 결과

이 파일들을 Claude Code 프로젝트 폴더에 `docs/` 디렉토리로 복사해두면 개발 중 참조할 수 있습니다.
