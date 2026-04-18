// 우리농 자가진단 체크리스트 — AI 분석 엔진 UI
// marked.js로 AI 응답(마크다운)을 렌더링합니다.

// ── 전역 상태 ──────────────────────────────────────
// 현재 분석의 cache_key (재분석 버튼용)
let currentCacheKey = { quick: null, verify: null };

// ── 탭 전환 ────────────────────────────────────────
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

// ── 파일명 미리보기 ────────────────────────────────
function bindFilename(inputId, labelId) {
  const input = document.getElementById(inputId);
  const label = document.getElementById(labelId);
  if (!input || !label) return;
  input.addEventListener("change", () => {
    if (input.files.length > 1) {
      label.textContent = `${input.files.length}개 파일 선택됨`;
    } else if (input.files.length === 1) {
      label.textContent = input.files[0].name;
    } else {
      label.textContent = "";
    }
  });
}
bindFilename("quick-pdf",   "quick-pdf-name");
bindFilename("verify-pdf",  "verify-pdf-name");
bindFilename("verify-docs", "verify-docs-name");

// ── 드래그앤드롭 (빠른 진단 dropzone) ──────────────
const drop   = document.getElementById("quick-drop");
const pdfIn  = document.getElementById("quick-pdf");
const pdfLbl = document.getElementById("quick-pdf-name");
if (drop) {
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("dragover"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("dragover"));
  drop.addEventListener("drop", e => {
    e.preventDefault();
    drop.classList.remove("dragover");
    const f = e.dataTransfer.files[0];
    if (f) {
      const dt = new DataTransfer();
      dt.items.add(f);
      pdfIn.files = dt.files;
      pdfLbl.textContent = f.name;
    }
  });
}

// ── 폼 제출 ────────────────────────────────────────
document.getElementById("quick-form").addEventListener("submit", async e => {
  e.preventDefault();
  await doAnalysis("quick", "/api/analyze-quick");
});
document.getElementById("verify-form").addEventListener("submit", async e => {
  e.preventDefault();
  await doAnalysis("verify", "/api/analyze-verify");
});

// ── 핵심 분석 함수 ──────────────────────────────────
async function doAnalysis(tab, endpoint, force = false) {
  const form   = document.getElementById(`${tab}-form`);
  const btn    = document.getElementById(`${tab}-submit-btn`);
  const area   = document.getElementById(`${tab}-result-area`);
  const content = document.getElementById(`${tab}-result-content`);
  const actions = document.getElementById(`${tab}-result-actions`);

  const url = force ? `${endpoint}?force=true` : endpoint;
  const fd  = new FormData(form);

  btn.disabled = true;
  btn.textContent = "분석 중…";
  showLoading(content, area);

  try {
    const resp = await fetch(url, { method: "POST", body: fd });
    const data = await resp.json();
    displayResult(data, tab, content, area, actions);
  } catch (err) {
    displayError(`서버 연결에 실패했습니다: ${err.message}`, content, area, actions);
  } finally {
    btn.disabled = false;
    btn.textContent = tab === "quick" ? "진단 시작" : "검증 시작";
  }
}

// ── 로딩 표시 ──────────────────────────────────────
function showLoading(content, area) {
  content.innerHTML = `
    <div class="loading-box">
      <div class="spinner"></div>
      <p>AI가 분석하고 있습니다…</p>
      <p class="loading-sub">규정 대조, 원재료 분석, 서류 점검 중 (약 30초~1분)</p>
    </div>`;
  area.style.display = "block";
  area.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── 결과 렌더링 ────────────────────────────────────
function displayResult(data, tab, content, area, actions) {
  if (data.error) {
    displayError(data.error, content, area, actions);
    return;
  }

  let html = "";

  // 캐시 알림 + 재분석 버튼
  if (data.cached) {
    html += `<div class="cache-notice">
      💾 이전 분석 결과입니다 (같은 파일 · 캐시)
    </div>`;
  }

  if (data.analysis) {
    // marked.js: 마크다운 → HTML
    marked.setOptions({ breaks: true, gfm: true });
    html += marked.parse(data.analysis);
  } else {
    html += `<p class="muted">분석 결과가 없습니다.</p>`;
  }

  content.innerHTML = html;
  area.style.display = "block";
  actions.style.display = "flex";

  // cache_key 저장 (재분석 버튼용)
  if (data.cache_key) currentCacheKey[tab] = data.cache_key;

  area.scrollIntoView({ behavior: "smooth", block: "start" });
}

function displayError(msg, content, area, actions) {
  content.innerHTML = `<div class="error-box"><strong>오류</strong><br>${esc(msg)}</div>`;
  area.style.display = "block";
  if (actions) actions.style.display = "none";
}

// ── 재분석 (force=true) ────────────────────────────
async function reanalyze(tab) {
  const endpoint = tab === "quick" ? "/api/analyze-quick" : "/api/analyze-verify";
  await doAnalysis(tab, endpoint, true);
}

// ── 초기화 (새 물품 분석하기) ──────────────────────
function resetForm(tab) {
  const form    = document.getElementById(`${tab}-form`);
  const area    = document.getElementById(`${tab}-result-area`);
  const content = document.getElementById(`${tab}-result-content`);
  const actions = document.getElementById(`${tab}-result-actions`);

  form.reset();
  // 파일명 표시 초기화
  ["quick-pdf-name","verify-pdf-name","verify-docs-name"]
    .forEach(id => { const el=document.getElementById(id); if(el) el.textContent=""; });

  content.innerHTML = "";
  area.style.display = "none";
  actions.style.display = "none";
  currentCacheKey[tab] = null;

  // 폼 상단으로 스크롤
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── 요청사항 복사 ──────────────────────────────────
function copyRequest(tab) {
  const content = document.getElementById(`${tab}-result-content`);
  if (!content) return;

  // "📨" 또는 "요청" 포함 heading 이후 텍스트 추출
  const headings = content.querySelectorAll("h4, h3");
  let reqText = "";
  for (const h of headings) {
    if (h.textContent.includes("요청") || h.textContent.includes("📨")) {
      let node = h.nextElementSibling;
      while (node && !["H3","H4"].includes(node.tagName)) {
        reqText += node.textContent + "\n";
        node = node.nextElementSibling;
      }
      break;
    }
  }

  const toCopy = reqText.trim() || content.textContent.trim();
  navigator.clipboard.writeText(toCopy).then(() => {
    alert(reqText ? "요청사항이 복사되었습니다!" : "분석 결과 전체가 복사되었습니다.");
  }).catch(() => {
    // 구형 브라우저 폴백
    const ta = document.createElement("textarea");
    ta.value = toCopy;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    alert("복사되었습니다!");
  });
}

// ── 이스케이프 ────────────────────────────────────
function esc(s) {
  return String(s ?? "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
