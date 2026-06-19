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

export function fileNameForPath(path) {
  const normalized = normalizeFilePath(path);
  if (!normalized) return "File";
  const parts = normalized.split("/").filter(Boolean);
  return parts[parts.length - 1] || normalized;
}

// Ported from reference/t3code/apps/web/src/components/files/filePath.ts so the
// breadcrumb shape stays one-to-one with T3code.
export function fileBreadcrumbs(projectName, relativePath) {
  const project = String(projectName || "").trim() || "Workspace";
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

const LANGUAGE_BY_EXTENSION = Object.freeze({
  c: "C",
  h: "C Header",
  cc: "C++",
  cpp: "C++",
  cxx: "C++",
  hpp: "C++ Header",
  hh: "C++ Header",
  py: "Python",
  js: "JavaScript",
  jsx: "JavaScript",
  mjs: "JavaScript",
  cjs: "JavaScript",
  ts: "TypeScript",
  tsx: "TypeScript",
  json: "JSON",
  md: "Markdown",
  mdx: "Markdown",
  css: "CSS",
  html: "HTML",
  sh: "Shell",
  ps1: "PowerShell",
  toml: "TOML",
  yml: "YAML",
  yaml: "YAML",
  txt: "Text",
});

export function fileLanguageForPath(path) {
  const name = fileNameForPath(path);
  const dot = name.lastIndexOf(".");
  if (dot <= 0) return "Plain";
  const ext = name.slice(dot + 1).toLowerCase();
  return LANGUAGE_BY_EXTENSION[ext] || ext.toUpperCase();
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

export function filePreviewMeta(content, path) {
  const lines = numberFileLines(content);
  return {
    lineCount: lines.length,
    charCount: String(content || "").length,
    language: fileLanguageForPath(path),
  };
}
