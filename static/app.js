// 우리농 자가진단 체크리스트 UI

// --- 탭 전환 ---
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
  });
});

// --- 드래그앤드롭 ---
const drop = document.getElementById("quick-drop");
const fileInput = document.getElementById("quick-file");
const filenameEl = document.getElementById("quick-filename");
if (drop) {
  drop.addEventListener("dragover", e => { e.preventDefault(); drop.classList.add("dragover"); });
  drop.addEventListener("dragleave", () => drop.classList.remove("dragover"));
  drop.addEventListener("drop", e => {
    e.preventDefault();
    drop.classList.remove("dragover");
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
      filenameEl.textContent = fileInput.files[0].name;
    }
  });
  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) filenameEl.textContent = fileInput.files[0].name;
  });
}

// --- 빠른 진단 ---
document.getElementById("quick-form").addEventListener("submit", async e => {
  e.preventDefault();
  if (!fileInput.files.length) { alert("파일을 선택해주세요"); return; }
  const fd = new FormData();
  fd.append("file", fileInput.files[0]);
  const result = document.getElementById("quick-result");
  result.innerHTML = '<div class="loading">진단 중입니다…</div>';
  try {
    const res = await fetch("/api/quick-diagnosis", { method: "POST", body: fd });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "오류");
    renderResult(result, data);
  } catch (err) {
    result.innerHTML = `<div class="error-msg">오류: ${err.message}</div>`;
  }
});

// --- 서류 검증 ---
document.getElementById("verify-form").addEventListener("submit", async e => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const result = document.getElementById("verify-result");
  result.innerHTML = '<div class="loading">검증 중입니다…</div>';
  try {
    const res = await fetch("/api/document-verification", { method: "POST", body: fd });
    const data = await res.json();
    if (!data.ok) throw new Error(data.error || "오류");
    renderResult(result, data);
  } catch (err) {
    result.innerHTML = `<div class="error-msg">오류: ${err.message}</div>`;
  }
});

// --- 결과 렌더링 ---
function renderResult(container, data) {
  const r = data.result;
  let html = "";

  // 제품 기본정보
  const pi = r.product_info || {};
  const fields = [
    ["제품명", pi.제품명],
    ["식품유형", pi.식품유형],
    ["제조원", pi.제조원],
    ["판매원", pi.판매원],
    ["생산자", pi.생산자],
    ["교구", pi.교구],
    ["회원구분", pi.회원구분],
    ["분과", pi.분과],
    ["내용량", pi.내용량],
    ["소비기한", pi.소비기한],
  ];
  html += `<div class="result-block"><h3>📦 제품 기본정보</h3><div class="info-grid">`;
  for (const [k, v] of fields) {
    if (v) html += `<div class="info-card"><div class="label">${k}</div><div class="value">${esc(v)}</div></div>`;
  }
  html += `</div></div>`;

  // 포장지 대조 (있을 때만)
  if (data.label_compare && data.label_compare.length) {
    html += `<div class="result-block"><h3>1️⃣ 포장지 ↔ 물품사양서 대조</h3><table class="compare-table"><thead><tr><th>항목</th><th>포장지</th><th>물품사양서</th><th>결과</th></tr></thead><tbody>`;
    for (const row of data.label_compare) {
      html += `<tr class="${row.status}"><td>${esc(row.field)}</td><td>${esc(row.label)}</td><td>${esc(row.spec)}</td><td>${row.icon}</td></tr>`;
    }
    html += `</tbody></table></div>`;
  }

  // 필요 서류
  html += section("📋 필요 서류 체크리스트", r.required_documents);
  // 기재 점검
  html += section("📝 물품사양서 기재 점검", r.spec_check, true);
  // 원재료 주의사항
  html += section("⚠️ 원재료 주의사항", r.ingredient_warnings);
  // 이슈 대비
  html += section("💡 출하 승인 시 예상 이슈", r.potential_issues);

  // 생산자 요청사항
  const reqs = r.request_to_producer || [];
  if (reqs.length) {
    const producer = pi.제조원 || pi.생산자 || "생산자";
    const textBlock =
`${producer} 님께,

우리농 신규물품 출하를 위해 아래 서류/정보가 추가로 필요합니다.

${reqs.map((s, i) => `${i + 1}. ${s}`).join("\n")}

확인 후 회신 부탁드립니다.
감사합니다.`;
    html += `<div class="result-block"><h3>📨 생산자에게 요청할 사항</h3><div class="request-box"><pre id="req-text">${esc(textBlock)}</pre><div class="btn-row"><button type="button" class="copy-btn" onclick="copyRequest()">📋 요청사항 복사</button>`;
    if (data.report_file) {
      html += `<a class="download-btn" href="/api/download/${encodeURIComponent(data.report_file)}" download>⬇ 엑셀 다운로드</a>`;
    }
    html += `</div></div></div>`;
  } else if (data.report_file) {
    html += `<div class="result-block"><a class="download-btn" href="/api/download/${encodeURIComponent(data.report_file)}" download>⬇ 엑셀 보고서 다운로드</a></div>`;
  }

  container.innerHTML = html;
}

function section(title, items, collapseOk) {
  if (!items || !items.length) return "";
  // collapseOk: '기재점검'처럼 OK 항목이 많은 섹션은 OK는 한 줄 요약
  let list = items;
  let okCount = 0;
  if (collapseOk) {
    okCount = items.filter(i => i.status === "ok").length;
    list = items.filter(i => i.status !== "ok");
  }
  let html = `<div class="result-block"><h3>${title}</h3>`;
  if (okCount > 0) {
    html += `<p class="ok-summary">${okCount}개 항목 정상 기재됨</p>`;
  }
  if (list.length) {
    html += `<ul class="checklist">`;
    for (const it of list) {
      html += `<li class="checklist-item ${it.status}">
        <span class="icon">${it.icon || ""}</span>
        <div class="body">
          <div class="title">${esc(it.title)}</div>
          ${it.description ? `<div class="description">${esc(it.description)}</div>` : ""}
          ${it.action ? `<div class="action">${esc(it.action)}</div>` : ""}
          ${it.regulation_ref ? `<div class="ref">근거: ${esc(it.regulation_ref)}</div>` : ""}
        </div>
      </li>`;
    }
    html += `</ul>`;
  }
  html += `</div>`;
  return html;
}

function copyRequest() {
  const t = document.getElementById("req-text").textContent;
  navigator.clipboard.writeText(t).then(() => {
    alert("요청사항이 복사되었습니다!");
  });
}

function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
