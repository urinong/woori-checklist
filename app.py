"""우리농 신규물품 출하 준비 자가진단 체크리스트 — Flask 앱"""
import os
import uuid
from flask import Flask, request, jsonify, render_template, send_from_directory

from config import (
    UPLOAD_DIR, OUTPUT_DIR, MAX_CONTENT_LENGTH,
    ALLOWED_EXTENSIONS, PORT, DEBUG,
)
from engine.pdf_parser import parse as parse_pdf
from engine.checklist_engine import ChecklistEngine
from engine.doc_matcher import classify_documents, verify_documents
from engine.image_reader import read_label_image
from engine.label_comparator import compare as label_compare
from engine.report_generator import generate as generate_report

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

engine = ChecklistEngine()


# -------------------- 유틸 --------------------

def _allowed(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS


def _safe_save(file_storage) -> str:
    """한글 파일명 지원: 확장자만 유지하고 UUID로 저장."""
    original = file_storage.filename or ""
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    name = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    path = os.path.join(UPLOAD_DIR, name)
    file_storage.save(path)
    return path


def _is_pdf(path: str) -> bool:
    return path.lower().endswith(".pdf")


def _is_image(path: str) -> bool:
    return any(path.lower().endswith(e) for e in (".jpg", ".jpeg", ".png"))


# -------------------- 라우트 --------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/quick-diagnosis", methods=["POST"])
def api_quick_diagnosis():
    """기능 A: 빠른 진단 — 포장지 사진 또는 물품사양서 PDF 하나"""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"error": "파일이 없습니다"}), 400
    if not _allowed(f.filename):
        return jsonify({"error": "지원하지 않는 파일 형식입니다 (PDF/JPG/PNG)"}), 400

    path = _safe_save(f)
    try:
        if _is_pdf(path):
            spec = parse_pdf(path)
            result = engine.diagnose(spec)
        else:
            # 포장지 이미지 → OCR → 간이 spec 생성
            label = read_label_image(path)
            from engine.pdf_parser import ProductSpec
            spec = ProductSpec()
            for k in ("제품명", "식품유형", "내용량", "보관방법", "알레르기물질",
                      "품목보고번호", "용기포장재질", "소비기한"):
                if isinstance(label, dict) and label.get(k):
                    setattr(spec, k, str(label[k]))
            spec.raw_text = (label.get("raw") if isinstance(label, dict) else "") or ""
            result = engine.diagnose(spec)

        # 엑셀 보고서 생성
        report_path = generate_report(result)
        return jsonify({
            "ok": True,
            "result": result.as_dict(),
            "report_file": os.path.basename(report_path),
        })
    except Exception as e:
        app.logger.exception("quick-diagnosis error")
        return jsonify({"error": f"진단 중 오류: {e}"}), 500


@app.route("/api/document-verification", methods=["POST"])
def api_document_verification():
    """기능 B: 서류 검증"""
    label_file = request.files.get("label")          # 포장지 이미지 (선택)
    spec_file = request.files.get("spec")            # 물품사양서 PDF (필수)
    docs = request.files.getlist("docs")             # 증빙서류 복수

    if not spec_file or not spec_file.filename:
        return jsonify({"error": "물품사양서 PDF는 필수입니다"}), 400

    spec_path = _safe_save(spec_file)
    try:
        spec = parse_pdf(spec_path)
    except Exception as e:
        return jsonify({"error": f"물품사양서 파싱 실패: {e}"}), 500

    # 포장지 OCR
    label_data = None
    compare_rows = []
    if label_file and label_file.filename:
        label_path = _safe_save(label_file)
        try:
            label_data = read_label_image(label_path)
            compare_rows = [
                {"field": r.field, "label": r.label_value, "spec": r.spec_value,
                 "status": r.status, "icon": r.icon}
                for r in label_compare(label_data, spec)
            ]
        except Exception as e:
            app.logger.warning(f"label OCR skip: {e}")

    # 증빙서류 분류
    doc_paths = []
    for d in docs or []:
        if d and d.filename and _allowed(d.filename):
            doc_paths.append(_safe_save(d))
    # 물품사양서도 포함
    all_doc_paths = [spec_path] + doc_paths
    matched = classify_documents(all_doc_paths)

    # 체크리스트 생성 → 서류 검증
    result = engine.diagnose(spec)
    verified = verify_documents(spec, result.required_documents, matched)
    result.required_documents = verified

    # 요청사항 재생성 (미제출 서류도 포함)
    extra_reqs = [it.action for it in verified if it.status in ("missing", "warning") and it.action]
    result.request_to_producer = list(dict.fromkeys(result.request_to_producer + extra_reqs))

    report_path = generate_report(result)
    return jsonify({
        "ok": True,
        "result": result.as_dict(),
        "label_compare": compare_rows,
        "matched_docs": [
            {"doc_type": m.doc_type, "file": m.source_file,
             "page_range": m.page_range, "product_name": m.product_name_found,
             "expiry": m.expiry_date}
            for m in matched
        ],
        "report_file": os.path.basename(report_path),
    })


@app.route("/api/download/<path:filename>")
def api_download(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)
