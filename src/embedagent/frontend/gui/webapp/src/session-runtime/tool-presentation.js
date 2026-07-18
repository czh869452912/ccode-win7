function text(value, fallback = "") {
  if (value == null) return fallback;
  return String(value).trim();
}

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

export function resolveToolPresentation(toolName, catalog = {}) {
  const name = text(toolName);
  const source = objectValue(objectValue(catalog)[name]);
  const metadata = objectValue(source.metadata);
  const declared = Boolean(name && objectValue(catalog)[name]);
  return {
    name,
    declared,
    label: text(source.label, name),
    iconKey: text(source.iconKey || source.icon_key, "wrench"),
    iconKeyDeclared: source.iconKeyDeclared !== undefined
      ? Boolean(source.iconKeyDeclared)
      : Boolean(text(source.iconKey || source.icon_key)),
    rendererKey: text(source.rendererKey || source.renderer_key, "generic"),
    permissionCategory: text(source.permissionCategory || source.permission_category, "other"),
    previewArg: text(metadata.previewArg || metadata.preview_arg),
    changedPathArg: text(metadata.changedPathArg || metadata.changed_path_arg),
    metadata,
  };
}

export function commandPreviewFromToolPresentation(presentation, args = {}) {
  const key = presentation && presentation.previewArg;
  if (!key) return "";
  const value = objectValue(args)[key];
  return text(value);
}
