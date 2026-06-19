import assert from "node:assert/strict";

import {
  FILE_PREVIEW_MODES,
  defaultFilePreviewMode,
  fileBreadcrumbs,
  fileLanguageForPath,
  fileNameForPath,
  filePreviewMeta,
  fileRevealLine,
  isMarkdownPreviewFile,
  normalizeFilePath,
  numberFileLines,
} from "../src/session-runtime/file-preview-model.js";

export function runFilePreviewModelTests() {
  assert.equal(normalizeFilePath("\\src\\parser.c"), "src/parser.c");
  assert.equal(normalizeFilePath("/a//b"), "a//b");
  assert.equal(fileNameForPath("src/deep/parser.c"), "parser.c");
  assert.equal(fileNameForPath(""), "File");

  const crumbs = fileBreadcrumbs("demo-app", "src/core/parser.c");
  assert.deepEqual(
    crumbs.map((crumb) => crumb.kind),
    ["project", "directory", "directory", "file"],
  );
  assert.equal(crumbs[0].label, "demo-app");
  assert.equal(crumbs[0].path, "");
  assert.equal(crumbs[2].path, "src/core");
  assert.equal(crumbs[3].label, "parser.c");
  assert.equal(crumbs[3].path, "src/core/parser.c");

  const rootCrumbs = fileBreadcrumbs("", "README.md");
  assert.equal(rootCrumbs[0].label, "Workspace");
  assert.equal(rootCrumbs.length, 2);
  assert.equal(rootCrumbs[1].kind, "file");

  assert.equal(isMarkdownPreviewFile("docs/readme.MD"), true);
  assert.equal(isMarkdownPreviewFile("notes.mdx"), true);
  assert.equal(isMarkdownPreviewFile("src/parser.c"), false);
  assert.equal(defaultFilePreviewMode("README.md"), FILE_PREVIEW_MODES.PREVIEW);
  assert.equal(defaultFilePreviewMode("src/parser.c"), FILE_PREVIEW_MODES.CODE);

  assert.equal(fileLanguageForPath("src/parser.c"), "C");
  assert.equal(fileLanguageForPath("app.tsx"), "TypeScript");
  assert.equal(fileLanguageForPath("Makefile"), "Plain");
  assert.equal(fileLanguageForPath("data.unknownext"), "UNKNOWNEXT");

  assert.deepEqual(numberFileLines(""), []);
  assert.deepEqual(numberFileLines("a\nb\n"), [
    { number: 1, text: "a" },
    { number: 2, text: "b" },
  ]);
  assert.deepEqual(numberFileLines("a\r\nb"), [
    { number: 1, text: "a" },
    { number: 2, text: "b" },
  ]);
  assert.equal(numberFileLines("only").length, 1);
  assert.equal(fileRevealLine("a\nb\nc\n", 2), 2);
  assert.equal(fileRevealLine("a\nb\nc\n", 99), 3);
  assert.equal(fileRevealLine("a\r\nb\rc", -4), 1);
  assert.equal(fileRevealLine("", 4), null);
  assert.equal(fileRevealLine("one", null), null);

  const meta = filePreviewMeta("int main(void);\nreturn 0;\n", "src/main.c");
  assert.equal(meta.lineCount, 2);
  assert.equal(meta.language, "C");
  assert.equal(meta.charCount, "int main(void);\nreturn 0;\n".length);

  console.log("file preview model checks passed");
}
