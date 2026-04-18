"""우리농 신규물품 출하 준비 자가진단 체크리스트 — Flask 앱

라우트:
  GET  /                       → 메인 페이지
  POST /api/analyze-quick      → 기능 A: AI 빠른 진단 (신규)
  POST /api/analyze-verify     → 기능 B: AI 서류 검증 (신규)
  GET  /api/download/<file>    → 엑셀 다운로드
"""
import os
import uuid
import base64

from flask import Flask, request, jsonify, render_template, send_from_directory

from config import (
    UPLOAD_DIR, OUTPUT_DIR, MAX_CONTENT_LENGTH,
    ALLOWED_EXTENSIONS, PORT, DEBUG,
)
from engine.pdf_parser import extract_text_from_pdf
from engine.ai_analyzer import analyze_quick_diagnosis, analyze_document_verification

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs("cache", exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH


# ─────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────

def _allowed(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS


def _safe_save(file_storage) -> str:
    """한글 파일명 지원: UUID 기반 저장."""
    original = file_storage.filename or ""
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    path = os.path.join(UPLOAD_DIR, name)
    file_storage.save(path)
    return path


def _file_to_b64(file_storage) -> dict:
    """이미지 파일 → base64 dict (Claude Vision용)"""
    data = base64.b64encode(file_storage.read()).decode("utf-8")
    mt = file_storage.content_type or "image/jpeg"
    return {"data": data, "media_type": mt}


# ─────────────────────────────────────────────────
# 라우트
# ─────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── 기능 A: AI 빠른 진단 ──────────────────────────

@app.route("/api/analyze-quick", methods=["POST"])
def analyze_quick():
    """기능 A: 빠른 진단 — AI 분석 엔진"""
    force = request.args.get("force", "").lower() == "true"

    # PDF 처리
    pdf_file = request.files.get("pdf_file")
    if not pdf_file or not pdf_file.filename or not _allowed(pdf_file.filename):
        return jsonify({"error": "파일이 없습니다. 물품사양서 PDF를 업로드해주세요."}), 400

    pdf_path = _safe_save(pdf_file)
    pdf_text = extract_text_from_pdf(pdf_path)

    result = analyze_quick_diagnosis(pdf_text=pdf_text, force=force)
    return jsonify(result)


# ── 기능 B: AI 서류 검증 ──────────────────────────

@app.route("/api/analyze-verify", methods=["POST"])
def analyze_verify():
    """기능 B: 서류 검증 — AI 분석 엔진"""
    force = request.args.get("force", "").lower() == "true"

    # 물품사양서 PDF (필수)
    pdf_file = request.files.get("pdf_file")
    if not pdf_file or not pdf_file.filename or not _allowed(pdf_file.filename):
        return jsonify({"error": "물품사양서 PDF를 업로드해주세요."}), 400

    pdf_path = _safe_save(pdf_file)
    pdf_text = extract_text_from_pdf(pdf_path)

    # 증빙서류 (복수 — PDF는 텍스트 추출, 이미지는 Vision으로 전달)
    docs = request.files.getlist("supporting_docs")
    doc_texts = []
    doc_images = []
    IMAGE_EXTS = {"jpg", "jpeg", "png"}
    for i, doc in enumerate(docs or []):
        if not doc or not doc.filename or not _allowed(doc.filename):
            continue
        ext = doc.filename.rsplit(".", 1)[-1].lower()
        if ext == "pdf":
            doc_path = _safe_save(doc)
            text = extract_text_from_pdf(doc_path)
            doc_texts.append(f"--- 증빙서류 {i+1}: {doc.filename} ---\n{text}")
        elif ext in IMAGE_EXTS:
            doc_images.append({**_file_to_b64(doc), "filename": doc.filename, "index": i+1})
    supporting_docs_text = "\n\n".join(doc_texts)

    result = analyze_document_verification(
        pdf_text=pdf_text,
        supporting_docs_text=supporting_docs_text,
        doc_images=doc_images or None,
        force=force,
    )
    return jsonify(result)


# ── 다운로드 ──────────────────────────────────────

@app.route("/api/download/<path:filename>")
def api_download(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
