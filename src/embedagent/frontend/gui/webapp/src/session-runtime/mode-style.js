const MODE_COLOR_TOKENS = {
  accent: { color: "var(--color-accent)", rgb: "188,140,255" },
  info: { color: "var(--color-info)", rgb: "56,139,253" },
  success: { color: "var(--color-success)", rgb: "63,185,80" },
  warning: { color: "var(--color-warning)", rgb: "210,153,34" },
  verify: { color: "var(--color-verify)", rgb: "227,179,65" },
};

function modeDescriptor(mode, catalog = {}) {
  return (catalog && catalog[mode]) || {};
}

function colorSpec(token) {
  return MODE_COLOR_TOKENS[token] || MODE_COLOR_TOKENS.info;
}

export function modeBadgeLabel(mode, catalog = {}) {
  const descriptor = modeDescriptor(mode, catalog);
  return descriptor.label || mode || "";
}

export function modeBadgeStyle(mode, catalog = {}) {
  const descriptor = modeDescriptor(mode, catalog);
  const spec = colorSpec(descriptor.colorToken || descriptor.color_token || "info");
  return {
    "--mode-badge-color": spec.color,
    "--mode-badge-rgb": spec.rgb,
  };
}
