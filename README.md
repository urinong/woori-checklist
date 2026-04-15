# 우리농 신규물품 출하 준비 자가진단 체크리스트

교구 실무자를 위한 신규물품 출하 서류 점검 도구입니다.
생산자/협력업체로부터 신규물품 출하 관련 서류를 요청·접수할 때, 우리농 생산규정에 맞는지 스스로 점검할 수 있도록 돕습니다.

## 기능

- **📋 빠른 진단**: 포장지 사진이나 물품사양서를 올리면 출하에 필요한 서류와 주의사항을 알려드려요.
- **✅ 서류 검증**: 받은 물품사양서와 증빙서류 합본을 올려 완비 여부와 내용 일치 여부를 점검합니다.

각 체크 항목에는 신입직원도 이해할 수 있는 설명과 "어떻게 요청할지" 액션 문구가 포함되어 있으며, 생산자에게 보낼 "요청사항" 텍스트 블록이 자동 생성되어 클립보드에 복사하거나 엑셀로 다운로드할 수 있습니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python app.py
# → http://localhost:5000
```

첫 실행 시 `data/` 디렉토리의 규정 엑셀 파일이 필요합니다. 새로 생성하려면:
```bash
python data/create_data.py
```

## 환경변수 (선택)

| 키 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | 설정 시 포장지 사진 OCR에 Claude Vision 사용. 미설정 시 Tesseract 폴백(설치 필요). |
| `PORT` | 서버 포트 (기본 5000). Render 등 PaaS에서 자동 설정. |
| `DEBUG` | `true` 지정 시 Flask 디버그 모드. 프로덕션은 `false`. |

## 프로젝트 구조

```
woori-review-app/
├── app.py                      # Flask 엔트리포인트
├── config.py                   # 환경 설정
├── Procfile                    # 배포(Render/Heroku)용 gunicorn 실행 명령
├── runtime.txt                 # Python 버전 지정
├── requirements.txt
│
├── data/                       # 규정 데이터 (엑셀)
│   ├── 제출서류_매핑.xlsx
│   ├── 원재료_기준.xlsx
│   ├── 첨가물_허용목록.xlsx
│   ├── GMO_목록.xlsx
│   ├── 수입허용원료.xlsx
│   ├── 표시사항_체크.xlsx
│   ├── 분과_매핑.xlsx
│   └── create_data.py          # 규정 엑셀 재생성 스크립트
│
├── engine/
│   ├── pdf_parser.py           # 물품사양서 PDF 파싱
│   ├── checklist_engine.py     # 체크리스트 생성 엔진
│   ├── doc_matcher.py          # 증빙서류 분류 및 검증
│   ├── image_reader.py         # 포장지 사진 OCR (Claude Vision / Tesseract)
│   ├── label_comparator.py     # 포장지 ↔ 물품사양서 대조
│   └── report_generator.py     # 엑셀 보고서 생성
│
├── templates/index.html        # 단일 페이지 UI (2탭)
├── static/
│   ├── style.css
│   └── app.js
├── uploads/                    # 업로드 임시 파일
└── outputs/                    # 생성된 엑셀 보고서
```

## 기술 스택

- **백엔드**: Python 3.11, Flask, pdfplumber, openpyxl, Pillow
- **배포**: gunicorn, Render (Singapore 리전 권장)
- **프론트**: Vanilla JS + CSS, Noto Sans KR (Google Fonts)

## 라이선스

가톨릭농민회 · 우리농촌살리기운동본부
