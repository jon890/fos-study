import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const renderer = fileURLToPath(new URL("./render_preview.mjs", import.meta.url));

function renderArticle(markdown) {
  const directory = mkdtempSync(path.join(tmpdir(), "blog-preview-test-"));
  try {
    const input = path.join(directory, "post.md");
    const output = path.join(directory, "preview.html");
    writeFileSync(input, markdown);
    execFileSync(process.execPath, [renderer, input, output]);
    return readFileSync(output, "utf8").match(/<article>([\s\S]*?)<\/article>/)[1];
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

test("renders numbered items as an ordered list", () => {
  assert.equal(
    renderArticle("1. **First**\n2. Second"),
    "<ol><li><strong>First</strong></li><li>Second</li></ol>",
  );
});

test("preserves the first number and restarts numbering for a new list", () => {
  assert.equal(
    renderArticle("3. Third\n4. Fourth\n\n1. First"),
    "<ol start=\"3\"><li>Third</li><li>Fourth</li></ol>\n<ol><li>First</li></ol>",
  );
});

test("keeps surrounding paragraphs in order", () => {
  assert.equal(
    renderArticle("Introduction\n1. First\n2. Second\nConclusion\nContinued"),
    "<p>Introduction</p>\n<ol><li>First</li><li>Second</li></ol>\n<p>Conclusion Continued</p>",
  );
});

test("keeps adjacent ordered and unordered lists separate", () => {
  assert.equal(
    renderArticle("- Dash\n* Asterisk\n1. First\n- Last"),
    "<ul><li>Dash</li><li>Asterisk</li></ul>\n<ol><li>First</li></ol>\n<ul><li>Last</li></ul>",
  );
});
