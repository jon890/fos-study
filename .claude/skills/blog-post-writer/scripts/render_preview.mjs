import fs from "node:fs/promises";
import path from "node:path";

const input = process.argv[2];
const output = process.argv[3];

if (!input || !output) {
  throw new Error("usage: node render_fos_blog_preview.mjs <input.md> <output.html>");
}

const markdown = await fs.readFile(input, "utf8");
const frontMatterMatch = markdown.match(/^---\s*\n([\s\S]*?)\n---\s*\n/);
const frontMatterBody = frontMatterMatch?.[1] ?? "";
const thumbnailPath = frontMatterBody.match(/^thumbnail:\s*["']?([^"'\n]+)["']?\s*$/m)?.[1]?.trim();
const markdownBody = frontMatterMatch ? markdown.slice(frontMatterMatch[0].length) : markdown;

async function thumbnailDataUrl() {
  if (!thumbnailPath || !thumbnailPath.startsWith("./")) return null;
  const absolutePath = path.resolve(path.dirname(input), thumbnailPath);
  try {
    const image = await fs.readFile(absolutePath);
    const extension = path.extname(absolutePath).toLowerCase();
    const mime = extension === ".png" ? "image/png" : extension === ".webp" ? "image/webp" : extension === ".avif" ? "image/avif" : "image/jpeg";
    return `data:${mime};base64,${image.toString("base64")}`;
  } catch {
    return null;
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderInline(value) {
  return escapeHtml(value)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

function renderTable(lines) {
  const rows = lines.map((line) => line.trim().slice(1, -1).split("|").map((cell) => cell.trim()));
  const head = rows[0] ?? [];
  const body = rows.slice(2);
  return [
    "<table>",
    "<thead><tr>",
    ...head.map((cell) => `<th>${renderInline(cell)}</th>`),
    "</tr></thead>",
    "<tbody>",
    ...body.map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell)}</td>`).join("")}</tr>`),
    "</tbody>",
    "</table>",
  ].join("");
}

function render(markdownText) {
  const lines = markdownText.split(/\r?\n/);
  const html = [];
  let index = 0;
  let codeLang = null;
  let codeLines = [];
  let listItems = [];
  let paragraphLines = [];

  function flushParagraph() {
    if (!paragraphLines.length) return;
    html.push(`<p>${renderInline(paragraphLines.join(" "))}</p>`);
    paragraphLines = [];
  }

  function flushList() {
    if (!listItems.length) return;
    html.push(`<ul>${listItems.map((item) => `<li>${renderInline(item)}</li>`).join("")}</ul>`);
    listItems = [];
  }

  while (index < lines.length) {
    const line = lines[index];
    const fence = line.match(/^```([A-Za-z0-9_-]+)?\s*$/);

    if (fence) {
      if (codeLang === null) {
        flushParagraph();
        flushList();
        codeLang = fence[1] ?? "";
        codeLines = [];
      } else {
        if (codeLang === "mermaid") {
          html.push(`<figure class="mermaid-preview"><figcaption>Mermaid diagram preview</figcaption><div class="mermaid">${escapeHtml(codeLines.join("\n"))}</div></figure>`);
        } else {
          html.push(`<pre><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
        }
        codeLang = null;
        codeLines = [];
      }
      index += 1;
      continue;
    }

    if (codeLang !== null) {
      codeLines.push(line);
      index += 1;
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      index += 1;
      continue;
    }

    if (/^\|.*\|$/.test(line) && index + 1 < lines.length && /^\|\s*-/.test(lines[index + 1])) {
      flushParagraph();
      flushList();
      const tableLines = [];
      while (index < lines.length && /^\|.*\|$/.test(lines[index])) {
        tableLines.push(lines[index]);
        index += 1;
      }
      html.push(renderTable(tableLines));
      continue;
    }

    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      flushParagraph();
      flushList();
      const level = heading[1].length;
      html.push(`<h${level}>${renderInline(heading[2])}</h${level}>`);
      index += 1;
      continue;
    }

    const listItem = line.match(/^[-*]\s+(.+)$/);
    if (listItem) {
      flushParagraph();
      listItems.push(listItem[1]);
      index += 1;
      continue;
    }

    if (line.startsWith("> ")) {
      flushParagraph();
      flushList();
      html.push(`<blockquote>${renderInline(line.slice(2))}</blockquote>`);
      index += 1;
      continue;
    }

    paragraphLines.push(line.trim());
    index += 1;
  }

  flushParagraph();
  flushList();
  return html.join("\n");
}

const title = markdownBody.match(/^#\s+(.+)$/m)?.[1] ?? "FOS Study Preview";
const content = render(markdownBody);
const thumbnail = await thumbnailDataUrl();
const html = `<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)} - FOS Study Preview</title>
  <style>
    :root {
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #0f172a;
      --muted: #64748b;
      --border: #e2e8f0;
      --accent: #2563eb;
      --code-bg: #0f172a;
      --code-text: #e2e8f0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.75;
    }
    header {
      border-bottom: 1px solid var(--border);
      background: rgba(255,255,255,.92);
      backdrop-filter: blur(12px);
      position: sticky;
      top: 0;
      z-index: 2;
    }
    .nav {
      max-width: 1120px;
      margin: 0 auto;
      padding: 14px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: var(--muted);
      font-size: 14px;
    }
    .brand {
      color: var(--text);
      font-weight: 700;
      letter-spacing: 0;
    }
    .wrap {
      max-width: 1120px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 230px;
      gap: 32px;
      padding: 36px 24px 80px;
    }
    article {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 44px 52px;
      box-shadow: 0 10px 28px rgba(15, 23, 42, .04);
    }
    .thumbnail-preview {
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
      border-radius: 10px;
      margin: 0 0 28px;
      border: 1px solid var(--border);
    }
    aside {
      color: var(--muted);
      font-size: 14px;
      padding-top: 10px;
    }
    h1 {
      font-size: 36px;
      line-height: 1.22;
      margin: 0 0 24px;
      letter-spacing: 0;
    }
    h2 {
      font-size: 25px;
      line-height: 1.35;
      margin: 48px 0 14px;
      padding-top: 26px;
      border-top: 1px solid var(--border);
      letter-spacing: 0;
    }
    p, ul, table, pre, blockquote, figure { margin-top: 16px; margin-bottom: 16px; }
    ul { padding-left: 24px; }
    li + li { margin-top: 6px; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    code {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: .92em;
      background: #eef2f7;
      color: #1e293b;
      border-radius: 5px;
      padding: 2px 5px;
    }
    pre {
      overflow: auto;
      background: var(--code-bg);
      color: var(--code-text);
      border-radius: 10px;
      padding: 18px 20px;
      line-height: 1.58;
    }
    pre code { background: transparent; color: inherit; padding: 0; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }
    th, td {
      border: 1px solid var(--border);
      padding: 10px 12px;
      vertical-align: top;
    }
    th { background: #f1f5f9; text-align: left; }
    blockquote {
      border-left: 4px solid #93c5fd;
      background: #eff6ff;
      color: #1e3a8a;
      padding: 10px 16px;
      border-radius: 0 8px 8px 0;
    }
    .mermaid-preview {
      border: 1px solid var(--border);
      background: #f8fafc;
      border-radius: 10px;
      padding: 14px;
    }
    .mermaid-preview figcaption {
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      margin-bottom: 10px;
    }
    .mermaid-preview .mermaid {
      display: flex;
      justify-content: center;
      overflow: auto;
      background: #fff;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 16px;
      min-height: 120px;
    }
    .mermaid-zoom-bar { display: flex; justify-content: flex-end; margin-top: 8px; }
    .mermaid-zoom-bar button {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border: 1px solid var(--border);
      background: #fff;
      color: var(--muted);
      border-radius: 6px;
      padding: 4px 8px;
      font: inherit;
      font-size: 12px;
      cursor: pointer;
    }
    .mermaid-zoom-bar button:hover { color: var(--text); border-color: #94a3b8; }
    .mermaid-modal {
      position: fixed;
      inset: 0;
      z-index: 50;
      background: rgba(15, 23, 42, 0.82);
      display: flex;
      flex-direction: column;
    }
    .mermaid-modal[hidden] { display: none; }
    .mermaid-modal-tools {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      padding: 12px 16px;
    }
    .mermaid-modal-tools button {
      width: 36px;
      height: 36px;
      border-radius: 8px;
      border: 1px solid rgba(255, 255, 255, 0.3);
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
      font-size: 16px;
      cursor: pointer;
    }
    .mermaid-modal-stage {
      flex: 1;
      overflow: hidden;
      touch-action: none;
      cursor: grab;
      position: relative;
    }
    .mermaid-modal-stage.is-panning { cursor: grabbing; }
    .mermaid-modal-content {
      transform-origin: 0 0;
      width: max-content;
    }
    .mermaid-modal-content svg { display: block; }
    .toc {
      position: sticky;
      top: 70px;
      border-left: 1px solid var(--border);
      padding-left: 16px;
    }
    .toc strong { color: var(--text); display: block; margin-bottom: 10px; }
    @media (max-width: 900px) {
      .wrap { display: block; padding: 24px 16px 64px; }
      article { padding: 30px 22px; }
      aside { display: none; }
      h1 { font-size: 29px; }
      h2 { font-size: 22px; }
    }
  </style>
</head>
<body>
  <header><div class="nav"><div class="brand">FOS Study</div><div>홈 · 카테고리 · 검색</div></div></header>
  <div class="wrap">
    <article>${thumbnail ? `<img class="thumbnail-preview" src="${thumbnail}" alt="">` : ""}${content}</article>
    <aside><div class="toc"><strong>Preview</strong><div>blog.fosworld.co.kr 스타일에 맞춘 로컬 HTML 미리보기입니다.</div></div></aside>
  </div>
  <div class="mermaid-modal" hidden role="dialog" aria-modal="true" aria-label="다이어그램 확대 보기">
    <div class="mermaid-modal-tools">
      <button type="button" data-act="out" aria-label="축소">&minus;</button>
      <button type="button" data-act="in" aria-label="확대">+</button>
      <button type="button" data-act="reset" aria-label="원래 크기로">&#8635;</button>
      <button type="button" data-act="close" aria-label="닫기">&times;</button>
    </div>
    <div class="mermaid-modal-stage"><div class="mermaid-modal-content"></div></div>
  </div>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
    mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose" });
    await mermaid.run();

    // 블로그의 MermaidZoomModal 과 같은 상수를 쓴다. 미리보기에서 본 확대 배율이
    // 실제 글에서 달라지면 미리보기의 의미가 없다.
    const MIN_SCALE = 0.5, MAX_SCALE = 12, MAX_INITIAL_SCALE = 6, SCALE_STEP = 1.5;
    const WHEEL_SENSITIVITY = 0.0015;

    const modal = document.querySelector(".mermaid-modal");
    const stage = modal.querySelector(".mermaid-modal-stage");
    const content = modal.querySelector(".mermaid-modal-content");
    let t = { scale: 1, x: 0, y: 0 };
    let baseScale = 1;
    let opener = null;

    const clamp = (v) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, v));

    // 확대 중심을 화면에 고정한 채 배율만 바꾼다.
    // transform 이 translate 뒤 scale 이므로 screen = x + s * c 이고,
    // 같은 좌표를 같은 자리에 남기려면 x' = p - s' * (p - x) / s 다.
    function zoomAt(nextScale, px, py) {
      const scale = clamp(nextScale);
      t = { scale, x: px - ((px - t.x) * scale) / t.scale, y: py - ((py - t.y) * scale) / t.scale };
      apply();
    }

    function apply() {
      content.style.transform = \`translate(\${t.x}px, \${t.y}px) scale(\${t.scale})\`;
    }

    function fit() {
      const box = stage.getBoundingClientRect();
      const svg = content.querySelector("svg");
      if (!svg) return;
      const w = svg.getBoundingClientRect().width / (t.scale || 1);
      const h = svg.getBoundingClientRect().height / (t.scale || 1);
      baseScale = clamp(Math.min(MAX_INITIAL_SCALE, Math.min(box.width / w, box.height / h)));
      t = {
        scale: baseScale,
        x: Math.max(0, (box.width - w * baseScale) / 2),
        y: Math.max(0, (box.height - h * baseScale) / 2),
      };
      apply();
    }

    function open(source, button) {
      opener = button;
      content.innerHTML = source.innerHTML;
      t = { scale: 1, x: 0, y: 0 };
      apply();
      modal.hidden = false;
      requestAnimationFrame(fit);
    }

    function close() {
      modal.hidden = true;
      content.innerHTML = "";
      if (opener) opener.focus();
    }

    // 확대 버튼을 다이어그램 아래 줄에 둔다. 위에 겹치면 낮은 다이어그램을 가린다.
    for (const fig of document.querySelectorAll(".mermaid-preview")) {
      const target = fig.querySelector(".mermaid");
      if (!target || !target.querySelector("svg")) continue;
      const bar = document.createElement("div");
      bar.className = "mermaid-zoom-bar";
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "확대";
      button.setAttribute("aria-label", "다이어그램 확대 보기");
      button.addEventListener("click", () => open(target, button));
      bar.append(button);
      fig.append(bar);
    }

    modal.querySelector(".mermaid-modal-tools").addEventListener("click", (e) => {
      const act = e.target.closest("button")?.dataset.act;
      if (!act) return;
      const box = stage.getBoundingClientRect();
      const cx = box.width / 2, cy = box.height / 2;
      if (act === "in") zoomAt(t.scale * SCALE_STEP, cx, cy);
      else if (act === "out") zoomAt(t.scale / SCALE_STEP, cx, cy);
      else if (act === "reset") fit();
      else close();
    });

    stage.addEventListener("wheel", (e) => {
      e.preventDefault();
      const box = stage.getBoundingClientRect();
      const factor = Math.exp(-e.deltaY * WHEEL_SENSITIVITY);
      zoomAt(t.scale * factor, e.clientX - box.left, e.clientY - box.top);
    }, { passive: false });

    let dragging = null;
    stage.addEventListener("pointerdown", (e) => {
      dragging = { id: e.pointerId, x: e.clientX, y: e.clientY };
      stage.setPointerCapture(e.pointerId);
      stage.classList.add("is-panning");
    });
    stage.addEventListener("pointermove", (e) => {
      if (!dragging || dragging.id !== e.pointerId) return;
      t = { ...t, x: t.x + (e.clientX - dragging.x), y: t.y + (e.clientY - dragging.y) };
      dragging = { ...dragging, x: e.clientX, y: e.clientY };
      apply();
    });
    for (const type of ["pointerup", "pointercancel"]) {
      stage.addEventListener(type, () => {
        dragging = null;
        stage.classList.remove("is-panning");
      });
    }

    document.addEventListener("keydown", (e) => {
      if (modal.hidden) return;
      const box = stage.getBoundingClientRect();
      const cx = box.width / 2, cy = box.height / 2;
      if (e.key === "Escape") close();
      else if (e.key === "+" || e.key === "=") zoomAt(t.scale * SCALE_STEP, cx, cy);
      else if (e.key === "-" || e.key === "_") zoomAt(t.scale / SCALE_STEP, cx, cy);
      else if (e.key === "0") fit();
      else return;
      e.preventDefault();
    });
  </script>
</body>
</html>`;

await fs.writeFile(output, html, "utf8");
