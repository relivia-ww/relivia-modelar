/**
 * Relívia Modelar — Editor Visual
 * contenteditable + MutationObserver + Gemini Image
 * JOB_ID e VERCEL_DOMAIN definidos no template editor.html
 */

// ── Estado ────────────────────────────────────────────────────────────────────
let _iframe      = null;
let _iframeDoc   = null;
let _codeMode    = false;
let _currentHtml = "";
let _selectedImg = null;
let _originalSrc = {};   // { imgSrc: originalSrc } para reverter
let _saveTimer   = null;
let _observer    = null;

// ── Init ──────────────────────────────────────────────────────────────────────
function onIframeLoad() {
  _iframe    = document.getElementById("preview-iframe");
  _iframeDoc = _iframe.contentDocument || _iframe.contentWindow.document;

  _injectContentEditable();
  _setupMutationObserver();
  _setupImageClickInterceptor();
  _setupFloatToolbar();

  // Captura HTML inicial
  _currentHtml = _iframeDoc.documentElement.outerHTML;
}

// ── contenteditable ───────────────────────────────────────────────────────────
function _injectContentEditable() {
  if (!_iframeDoc) return;
  const body = _iframeDoc.body;
  if (!body) return;

  // Injeta contenteditable em todos os elementos de texto relevantes
  const selectors = ["p", "h1", "h2", "h3", "h4", "h5", "h6", "span", "li", "td", "th", "blockquote", "div:not([contenteditable])"];
  selectors.forEach(sel => {
    _iframeDoc.querySelectorAll(sel).forEach(el => {
      // Só elementos com texto direto (sem filhos com mais elementos de texto)
      if (el.children.length === 0 && el.textContent.trim()) {
        el.setAttribute("contenteditable", "true");
        el.style.outline = "none";
        el.style.cursor = "text";
        el.addEventListener("focus", () => el.style.outline = "2px solid rgba(46,43,255,.3)");
        el.addEventListener("blur",  () => { el.style.outline = "none"; triggerSave(); });
      }
    });
  });
}

// ── MutationObserver ──────────────────────────────────────────────────────────
function _setupMutationObserver() {
  if (!_iframeDoc || !_iframeDoc.body) return;
  if (_observer) _observer.disconnect();

  _observer = new MutationObserver(_debounce(() => {
    _currentHtml = _iframeDoc.documentElement.outerHTML;
  }, 300));

  _observer.observe(_iframeDoc.body, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["src", "href", "style", "class"],
  });
}

// ── Image click interceptor ───────────────────────────────────────────────────
function _setupImageClickInterceptor() {
  if (!_iframeDoc) return;

  _iframeDoc.querySelectorAll("img").forEach(img => {
    img.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      _selectImage(img);
    });
    img.style.cursor = "pointer";

    // Hover outline
    img.addEventListener("mouseenter", () => img.style.outline = "3px solid var(--blue, #2E2BFF)");
    img.addEventListener("mouseleave", () => {
      if (_selectedImg !== img) img.style.outline = "";
    });
  });
}

function _selectImage(img) {
  // Remove outline de imagem anterior
  if (_selectedImg && _selectedImg !== img) {
    _selectedImg.style.outline = "";
  }
  _selectedImg = img;
  img.style.outline = "3px solid #2E2BFF";

  // Guarda src original para poder reverter
  if (!_originalSrc[img.src]) {
    _originalSrc[img.src] = img.src;
  }

  // Mostra painel Gemini
  showTab("gemini");
  document.getElementById("no-img-selected").style.display = "none";
  document.getElementById("img-selected").style.display = "block";
  document.getElementById("img-preview").src = img.src;
  document.getElementById("gemini-status").textContent = "";
  document.getElementById("gemini-prompt").value = "";
}

// ── Float toolbar (bold/italic/underline) ─────────────────────────────────────
function _setupFloatToolbar() {
  const toolbar = document.getElementById("float-toolbar");
  if (!_iframeDoc) return;

  _iframeDoc.addEventListener("selectionchange", () => {
    const sel = _iframeDoc.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      toolbar.style.display = "none";
      return;
    }

    // Posiciona acima da seleção
    const range = sel.getRangeAt(0);
    const rect  = range.getBoundingClientRect();
    const iRect = _iframe.getBoundingClientRect();

    toolbar.style.display = "flex";
    toolbar.style.left = (iRect.left + rect.left + rect.width / 2 - 50) + "px";
    toolbar.style.top  = (iRect.top  + rect.top  - 44) + "px";
    toolbar.style.position = "fixed";
  });
}

function execCmd(cmd) {
  if (!_iframeDoc) return;
  _iframeDoc.execCommand(cmd, false, null);
  triggerSave();
}

// ── Auto-save ─────────────────────────────────────────────────────────────────
function triggerSave() {
  clearTimeout(_saveTimer);
  _saveTimer = setTimeout(saveHtml, 2000);
}

async function saveHtml() {
  const html = _codeMode
    ? document.getElementById("code-editor").value
    : (_iframeDoc ? _iframeDoc.documentElement.outerHTML : _currentHtml);

  if (!html) return;
  _currentHtml = html;

  const statusEl = document.getElementById("save-status");
  statusEl.textContent = "Salvando…";

  try {
    const r = await fetch(`/editor/${JOB_ID}/save`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ html }),
    });
    const d = await r.json();
    statusEl.textContent = d.ok ? "✅ Salvo" : "❌ Erro ao salvar";
    setTimeout(() => { statusEl.textContent = ""; }, 3000);
  } catch(e) {
    statusEl.textContent = "❌ Erro de rede";
  }
}

// ── Modo código ───────────────────────────────────────────────────────────────
function toggleCode() {
  _codeMode = !_codeMode;
  const iframe = document.getElementById("preview-iframe");
  const code   = document.getElementById("code-editor");
  const btn    = document.querySelector(".tool-btn-secondary");

  if (_codeMode) {
    // Visual → Código
    const html = _iframeDoc ? _iframeDoc.documentElement.outerHTML : _currentHtml;
    code.value = html;
    iframe.style.display = "none";
    code.style.display   = "block";
    document.querySelectorAll(".tool-btn-secondary")[0].textContent = "Ver visual";
  } else {
    // Código → Visual
    const html = code.value;
    iframe.style.display = "block";
    code.style.display   = "none";
    document.querySelectorAll(".tool-btn-secondary")[0].textContent = "Ver código";

    // Recarrega iframe com novo HTML
    const blob = new Blob([html], { type: "text/html" });
    const url  = URL.createObjectURL(blob);
    iframe.src = url;
    iframe.onload = () => {
      URL.revokeObjectURL(url);
      onIframeLoad();
    };
  }
}

// ── Gemini Image ──────────────────────────────────────────────────────────────
async function generateImage() {
  if (!_selectedImg) return;
  const prompt = document.getElementById("gemini-prompt").value.trim();
  if (!prompt) { alert("Digite um prompt para editar a imagem."); return; }

  const btn    = document.getElementById("btn-generate");
  const status = document.getElementById("gemini-status");

  btn.disabled    = true;
  btn.textContent = "Gerando…";
  status.textContent = "Enviando para Gemini…";

  // Extrai nome do arquivo da src
  const src      = _selectedImg.src;
  const imgName  = src.split("/").pop().split("?")[0];

  try {
    const r = await fetch(`/editor/${JOB_ID}/generate-image`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, image_name: imgName }),
    });
    const d = await r.json();

    if (d.error) {
      status.textContent = "❌ " + d.error;
      status.style.color = "#ef4444";
    } else {
      // Substitui src no iframe
      _selectedImg.src = d.data_uri;
      document.getElementById("img-preview").src = d.data_uri;
      status.textContent = "✅ Imagem gerada!";
      status.style.color = "#166534";
      triggerSave();
    }
  } catch(e) {
    status.textContent = "❌ Erro de rede: " + e.message;
    status.style.color = "#ef4444";
  } finally {
    btn.disabled    = false;
    btn.textContent = "Gerar IA";
  }
}

function revertImage() {
  if (!_selectedImg) return;
  const orig = _originalSrc[_selectedImg.getAttribute("data-original-src") || _selectedImg.src];
  if (orig) {
    _selectedImg.src = orig;
    document.getElementById("img-preview").src = orig;
    document.getElementById("gemini-status").textContent = "↩ Revertida para original";
    document.getElementById("gemini-status").style.color = "var(--muted)";
    triggerSave();
  }
}

// ── Publicar ──────────────────────────────────────────────────────────────────
async function publishJob() {
  const btn    = document.getElementById("btn-publish");
  const result = document.getElementById("publish-result");

  btn.disabled    = true;
  btn.textContent = "⏳ Publicando…";
  result.innerHTML = "";

  // Salva primeiro
  await saveHtml();

  try {
    const r = await fetch(`/publicar/${JOB_ID}`, { method: "POST" });
    const d = await r.json();

    if (d.error) {
      result.innerHTML = `<div class="pub-result error">❌ ${d.error}</div>`;
      btn.disabled = false; btn.textContent = "☁ Publicar agora";
      return;
    }

    let html = `<div class="pub-result success">
      ✅ <strong>${d.committed} arquivo${d.committed !== 1 ? "s" : ""} publicados</strong>`;
    if (d.commit_url) html += `<br><a href="${d.commit_url}" target="_blank" style="color:#166534">Ver commit no GitHub ↗</a>`;
    if (d.published_url) html += `<br><a href="${d.published_url}" target="_blank" style="color:#166534">Ver página publicada ↗</a>`;
    if (d.vercel_status) html += `<br><small>Vercel: ${d.vercel_status}</small>`;
    html += `</div>`;
    result.innerHTML = html;
    btn.textContent = "✅ Publicado";

  } catch(e) {
    result.innerHTML = `<div class="pub-result error">❌ Erro de rede: ${e.message}</div>`;
    btn.disabled = false; btn.textContent = "☁ Publicar agora";
  }
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function showTab(tab) {
  document.getElementById("panel-gemini").style.display  = tab === "gemini"  ? "block" : "none";
  document.getElementById("panel-publish").style.display = tab === "publish" ? "block" : "none";
  document.getElementById("tab-gemini").classList.toggle("active",  tab === "gemini");
  document.getElementById("tab-publish").classList.toggle("active", tab === "publish");
}

function showPublishPanel() { showTab("publish"); }

// ── Utils ─────────────────────────────────────────────────────────────────────
function _debounce(fn, delay) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), delay); };
}
