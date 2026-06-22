import fs from "node:fs/promises";

const input = process.argv[2];
const output = process.argv[3];

if (!input || !output) {
  throw new Error("usage: node render_fos_blog_preview.mjs <input.md> <output.html>");
}

const markdown = await fs.readFile(input, "utf8");

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

const title = markdown.match(/^#\s+(.+)$/m)?.[1] ?? "FOS Study Preview";
const content = render(markdown);
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
    <article>${content}</article>
    <aside><div class="toc"><strong>Preview</strong><div>blog.fosworld.co.kr 스타일에 맞춘 로컬 HTML 미리보기입니다.</div></div></aside>
  </div>
  <script type="module">
    import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
    mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
  </script>
</body>
</html>`;

await fs.writeFile(output, html, "utf8");
