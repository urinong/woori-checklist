"""우리농 신규물품 출하 준비 자가진단 체크리스트 — 설정"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB

PORT = int(os.environ.get("PORT", 5000))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# 규정 데이터 엑셀 경로
DATA_FILES = {
    "제출서류": os.path.join(DATA_DIR, "제출서류_매핑.xlsx"),
    "원재료": os.path.join(DATA_DIR, "원재료_기준.xlsx"),
    "첨가물": os.path.join(DATA_DIR, "첨가물_허용목록.xlsx"),
    "GMO": os.path.join(DATA_DIR, "GMO_목록.xlsx"),
    "수입허용": os.path.join(DATA_DIR, "수입허용원료.xlsx"),
    "표시사항": os.path.join(DATA_DIR, "표시사항_체크.xlsx"),
    "분과": os.path.join(DATA_DIR, "분과_매핑.xlsx"),
}

# 포장지 OCR — Claude API 사용 여부 (환경변수 ANTHROPIC_API_KEY 있으면 활성화)
USE_CLAUDE_VISION = bool(os.environ.get("ANTHROPIC_API_KEY"))
