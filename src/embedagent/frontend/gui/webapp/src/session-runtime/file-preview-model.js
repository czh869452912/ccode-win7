// GUI-local file-preview presentation model.
//
// These helpers project an already-loaded file preview ({ path, content })
// into the display chrome the T3code file viewer shows: a project/dir/file
// breadcrumb trail, a code/markdown preview mode, a numbered code gutter, and
// lightweight language/line metadata. This is GUI app-shell read-model work:
// it never mutates files, writes transcript history, or touches Agent Core,
// backend protocol, workflow state, permission policy, or runtime reducers.

export const FILE_PREVIEW_MODES = Object.freeze({
  CODE: "code",
  PREVIEW: "preview",
});

export function normalizeFilePath(path) {
  return String(path || "")
    .replace(/\\/g, "/")
    .replace(/^\/+/, "");
}

export function fileNameForPath(path, chrome = {}) {
  const normalized = normalizeFilePath(path);
  if (!normalized) return chrome.defaultFileTitle || "";
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] || normalized;
}

// Ported from reference/t3code/apps/web/src/components/files/filePath.ts so the
// breadcrumb shape stays one-to-one with T3code.
export function fileBreadcrumbs(projectName, relativePath, chrome = {}) {
  const project = String(projectName || "").trim() || chrome.defaultProjectLabel || "";
  const parts = normalizeFilePath(relativePath).split("/").filter(Boolean);
  return [
    { label: project, path: "", kind: "project" },
    ...parts.map((part, index) => ({
      label: part,
      path: parts.slice(0, index + 1).join("/"),
      kind: index === parts.length - 1 ? "file" : "directory",
    })),
  ];
}

// Ported from reference/t3code/apps/web/src/components/files/filePreviewMode.ts.
export function isMarkdownPreviewFile(path) {
  return /\.(?:md|mdx)$/i.test(normalizeFilePath(path));
}

export function defaultFilePreviewMode(path) {
  return isMarkdownPreviewFile(path) ? FILE_PREVIEW_MODES.PREVIEW : FILE_PREVIEW_MODES.CODE;
}

const LANGUAGE_KEY_BY_EXTENSION = Object.freeze({
  c: "c",
  h: "c_header",
  cc: "cpp",
  cpp: "cpp",
  cxx: "cpp",
  hpp: "cpp_header",
  hh: "cpp_header",
  py: "python",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  ts: "typescript",
  tsx: "typescript",
  json: "json",
  md: "markdown",
  mdx: "markdown",
  css: "css",
  html: "html",
  sh: "shell",
  ps1: "powershell",
  toml: "toml",
  yml: "yaml",
  yaml: "yaml",
  txt: "text",
});

export function fileLanguageForPath(path, chrome = {}) {
  const name = fileNameForPath(path, chrome);
  const dot = name.lastIndexOf(".");
  if (dot <= 0) return chrome.plainLanguageLabel || "";
  const ext = name.slice(dot + 1).toLowerCase();
  const labelKey = LANGUAGE_KEY_BY_EXTENSION[ext] || "";
  const labels = chrome.languageLabels && typeof chrome.languageLabels === "object"
    ? chrome.languageLabels
    : {};
  return (labelKey && labels[labelKey]) || ext.toUpperCase();
}

// Split file content into numbered gutter rows. Handles CRLF/CR/LF uniformly
// and drops a single trailing newline so an N-line file shows N rows rather
// than a phantom blank final row.
export function numberFileLines(content) {
  const text = String(content || "");
  if (text === "") return [];
  const normalized = text.replace(/\r\n?/g, "\n");
  const body = normalized.endsWith("\n") ? normalized.slice(0, -1) : normalized;
  return body.split("\n").map((line, index) => ({ number: index + 1, text: line }));
}

// Mirrors T3code's clampFileLine behavior for file-link reveal requests:
// invalid/no request means no reveal, otherwise clamp to the visible file range.
export function fileRevealLine(content, requestedLine) {
  if (requestedLine === null || requestedLine === undefined || requestedLine === "") return null;
  const value = Number(requestedLine);
  if (!Number.isFinite(value)) return null;
  const lines = numberFileLines(content);
  if (lines.length === 0) return null;
  return Math.min(Math.max(1, Math.trunc(value)), lines.length);
}

export function filePreviewMeta(content, path, chrome = {}) {
  const lines = numberFileLines(content);
  return {
    lineCount: lines.length,
    charCount: String(content || "").length,
    language: fileLanguageForPath(path, chrome),
  };
}
