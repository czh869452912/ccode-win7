import React from "react";

function FieldList({ fields = [] }) {
  if (!Array.isArray(fields) || fields.length === 0) return null;
  return (
    <dl className="t3-tool-detail-grid">
      {fields.map((field) => (
        <React.Fragment key={`${field.label}-${field.value}`}>
          <dt>{field.label}</dt>
          <dd className={field.mono === false ? "" : "mono"}>{field.value}</dd>
        </React.Fragment>
      ))}
    </dl>
  );
}

function MatchItems({ items = [] }) {
  return (
    <div className="t3-tool-detail-list">
      {items.map((item) => (
        <div key={item.id || `${item.path}-${item.line}-${item.text}`} className="t3-tool-detail-item">
          <span className="t3-tool-detail-item-path">
            {[item.path, item.line ? `:${item.line}` : ""].filter(Boolean).join("") || "match"}
          </span>
          {item.text ? <code>{item.text}</code> : null}
        </div>
      ))}
    </div>
  );
}

function FileItems({ items = [] }) {
  return (
    <div className="t3-tool-detail-files">
      {items.map((item) => (
        <span key={item.id || item.path} className="t3-work-file">
          {item.path}
          {item.additions || item.deletions ? (
            <small> +{item.additions || 0} -{item.deletions || 0}</small>
          ) : null}
        </span>
      ))}
    </div>
  );
}

function Section({ section }) {
  if (!section) return null;
  const isDiff = section.kind === "diff";
  const isOutput = section.kind === "stdout" || section.kind === "stderr" || section.kind === "error";
  return (
    <section className={`t3-tool-detail-section ${section.kind || "text"}`}>
      <div className="t3-tool-detail-section-title">{section.title || section.kind || "Detail"}</div>
      {section.kind === "matches" ? <MatchItems items={section.items || []} /> : null}
      {section.kind === "files" || section.kind === "changed_files" ? <FileItems items={section.items || []} /> : null}
      {section.content ? (
        <pre className={isDiff ? "diff" : isOutput ? "output" : ""}>{section.content}</pre>
      ) : null}
    </section>
  );
}

export default function ToolDetail({ model }) {
  if (!model) return null;
  const sections = Array.isArray(model.sections) ? model.sections : [];
  return (
    <div className="t3-tool-detail" data-testid="timeline-tool-detail">
      <FieldList fields={model.fields || []} />
      {sections.map((section, index) => (
        <Section key={`${section.kind || "section"}-${index}`} section={section} />
      ))}
    </div>
  );
}
