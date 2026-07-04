import React from "react";

function fieldLabel(field, chrome = {}) {
  const key = String(field?.key || field?.label || "");
  const labels = chrome.fieldLabels || {};
  return labels[key] || field?.label || key;
}

function sectionTitle(section, chrome = {}) {
  const key = String(section?.kind || "");
  const titles = chrome.sectionTitles || {};
  return titles[key] || section?.title || key || chrome.defaultSectionTitle || "";
}

function fallbackMatchLabel(chrome = {}) {
  return chrome.fallbackMatchLabel || "";
}

function FieldList({ fields = [], chrome = {} }) {
  if (!Array.isArray(fields) || fields.length === 0) return null;
  return (
    <dl className="t3-tool-detail-grid">
      {fields.map((field) => (
        <React.Fragment key={`${field.key || field.label}-${field.value}`}>
          <dt>{fieldLabel(field, chrome)}</dt>
          <dd className={field.mono === false ? "" : "mono"}>{field.value}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function FileTargetButton({ item, onOpenFile, children }) {
  if (!item?.path || !onOpenFile) {
    return <span className="t3-tool-detail-item-path">{children}</span>;
  }
  return (
    <button
      type="button"
      className="t3-tool-detail-item-path timeline-file-link"
      data-testid={`timeline-tool-file-link--${item.path}`}
      onClick={() => onOpenFile(item.path, item.line || undefined)}
    >
      {children}
    </button>
  );
}

function MatchItems({ items = [], onOpenFile = null, chrome = {} }) {
  return (
    <div className="t3-tool-detail-list">
      {items.map((item) => {
        const label = [item.path, item.displayLine || item.line ? `:${item.displayLine || item.line}` : ""]
          .filter(Boolean)
          .join("") || fallbackMatchLabel(chrome);
        return (
          <div key={item.id || `${item.path}-${item.line}-${item.text}`} className="t3-tool-detail-item">
            <FileTargetButton item={item} onOpenFile={onOpenFile}>{label}</FileTargetButton>
            {item.text ? <code>{item.text}</code> : null}
          </div>
        );
      })}
    </div>
  );
}

function FileItems({ items = [], onOpenFile = null }) {
  return (
    <div className="t3-tool-detail-files">
      {items.map((item) => (
        <FileTargetButton key={item.id || item.path} item={item} onOpenFile={onOpenFile}>
          {item.path}
          {item.additions || item.deletions ? (
            <small> +{item.additions || 0} -{item.deletions || 0}</small>
          ) : null}
        </FileTargetButton>
      ))}
    </div>
  );
}

function Section({ section, onOpenFile, chrome = {} }) {
  if (!section) return null;
  const isDiff = section.kind === "diff";
  const isOutput = section.kind === "stdout" || section.kind === "stderr" || section.kind === "error";
  return (
    <section className={`t3-tool-detail-section ${section.kind || "text"}`}>
      <div className="t3-tool-detail-section-title">{sectionTitle(section, chrome)}</div>
      {section.kind === "matches" ? (
        <MatchItems items={section.items || []} onOpenFile={onOpenFile} chrome={chrome} />
      ) : null}
      {section.kind === "files" || section.kind === "changed_files" ? <FileItems items={section.items || []} onOpenFile={onOpenFile} /> : null}
      {section.content ? (
        <pre className={isDiff ? "diff" : isOutput ? "output" : ""}>{section.content}</pre>
      ) : null}
    </section>
  );
}

export default function ToolDetail({ model, onOpenFile = null, chrome = {} }) {
  if (!model) return null;
  const sections = Array.isArray(model.sections) ? model.sections : [];
  return (
    <div className="t3-tool-detail" data-testid="timeline-tool-detail">
      <FieldList fields={model.fields || []} chrome={chrome} />
      {sections.map((section, index) => (
        <Section
          key={`${section.kind || "section"}-${index}`}
          section={section}
          onOpenFile={onOpenFile}
          chrome={chrome}
        />
      ))}
    </div>
  );
}
