import React from "react";
import { RIGHT_PANEL_SURFACES, titleForSurfaceKind } from "../../workbench/surfaces.js";

const SURFACE_COPY = {
  diff: {
    icon: "D",
    label: "Diff",
    description: "Review local changes.",
  },
  files: {
    icon: "F",
    label: "Files",
    description: "Browse workspace files.",
  },
  file: {
    icon: "F",
    label: "File",
    description: "View a workspace file.",
  },
  terminal: {
    icon: "T",
    label: "Terminal",
    description: "Use a shell in this workspace.",
  },
  plan: {
    icon: "P",
    label: "Plan",
    description: "Inspect the current plan.",
  },
};

const SURFACE_TAB_TEST_IDS = {
  file: "right-panel-surface-tab--file",
};

function surfaceTitle(surface) {
  if (!surface) return "";
  if (surface.title) return surface.title;
  return titleForSurfaceKind(surface.kind);
}

function SurfaceIcon({ kind }) {
  const copy = SURFACE_COPY[kind] || { icon: "S" };
  return <span className="right-panel-surface-icon" aria-hidden="true">{copy.icon}</span>;
}

function SurfaceTabMenu({
  surface,
  onCloseOtherSurfaces,
  onCloseSurfacesToRight,
  onCloseAllSurfaces,
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <span className="right-panel-tab-menu">
      <button
        type="button"
        className="right-panel-tab-menu-button"
        aria-label={`Surface actions for ${surfaceTitle(surface)}`}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        ...
      </button>
      {open ? (
        <span className="right-panel-tab-menu-popup" role="menu">
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onCloseOtherSurfaces(surface);
            }}
          >
            Close others
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onCloseSurfacesToRight(surface);
            }}
          >
            Close to the right
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onCloseAllSurfaces();
            }}
          >
            Close all
          </button>
        </span>
      ) : null}
    </span>
  );
}

function SurfaceAddMenu({ onAddSurface }) {
  const [open, setOpen] = React.useState(false);
  const availableSurfaces = RIGHT_PANEL_SURFACES.slice();
  return (
    <span className="right-panel-add-menu">
      <button
        type="button"
        className="right-panel-add-surface"
        aria-label="Add panel surface"
        onClick={() => setOpen((value) => !value)}
        title="Add panel surface"
      >
        +
      </button>
      {open ? (
        <span className="right-panel-add-menu-popup" role="menu">
          {availableSurfaces.map((kind) => {
            const copy = SURFACE_COPY[kind];
            return (
              <button
                key={kind}
                type="button"
                role="menuitem"
                onClick={() => {
                  setOpen(false);
                  onAddSurface(kind);
                }}
              >
                <SurfaceIcon kind={kind} />
                <span>{copy.label}</span>
              </button>
            );
          })}
        </span>
      ) : null}
    </span>
  );
}

function RightPanelEmptyState({ onAddSurface }) {
  const availableSurfaces = RIGHT_PANEL_SURFACES.slice();
  return (
    <div className="right-panel-empty-state" data-testid="right-panel-empty-state">
      <div className="right-panel-empty-copy">
        <h3>Open a surface</h3>
        <p>Choose what to show in the right panel.</p>
      </div>
      <div className="right-panel-empty-grid">
        {availableSurfaces.map((kind) => {
          const copy = SURFACE_COPY[kind];
          return (
            <button
              key={kind}
              type="button"
              className="right-panel-empty-card"
              onClick={() => onAddSurface(kind)}
              data-testid={`right-panel-empty-surface--${kind}`}
            >
              <SurfaceIcon kind={kind} />
              <span>{copy.label}</span>
              <small>{copy.description}</small>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function RightPanelTabs({
  surfaces,
  activeSurfaceId,
  onActivateSurface,
  onCloseSurface,
  onCloseOtherSurfaces,
  onCloseSurfacesToRight,
  onCloseAllSurfaces,
  onAddSurface,
  children,
}) {
  const items = Array.isArray(surfaces) ? surfaces : [];
  const activeSurface = items.find((surface) => surface.id === activeSurfaceId) || null;
  const tabListRef = React.useRef(null);
  React.useEffect(() => {
    const activeTab = tabListRef.current?.querySelector("[data-active-tab='true']");
    activeTab?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [activeSurfaceId]);

  return (
    <aside className="right-panel" role="complementary" aria-label="Right panel" data-testid="right-panel">
      <div className="right-panel-tabs" role="tablist" data-testid="right-panel-surface-tabs">
        <div className="right-panel-tab-scroll" ref={tabListRef} data-right-panel-tab-list>
          {items.map((surface) => {
            const active = surface.id === activeSurfaceId;
            const title = surfaceTitle(surface);
            return (
              <div
                key={surface.id}
                className={`right-panel-surface-tab${active ? " active" : ""}`}
                data-active-tab={active ? "true" : "false"}
                data-testid={SURFACE_TAB_TEST_IDS[surface.kind] || `right-panel-surface-tab--${surface.kind}`}
              >
                <button
                  type="button"
                  role="tab"
                  aria-selected={active}
                  className="right-panel-surface-tab-main"
                  title={title}
                  onClick={() => onActivateSurface(surface)}
                >
                  <SurfaceIcon kind={surface.kind} />
                  <span>{title}</span>
                </button>
                <SurfaceTabMenu
                  surface={surface}
                  onCloseOtherSurfaces={onCloseOtherSurfaces}
                  onCloseSurfacesToRight={onCloseSurfacesToRight}
                  onCloseAllSurfaces={onCloseAllSurfaces}
                />
                <button
                  type="button"
                  className="right-panel-tab-close"
                  aria-label={`Close ${title}`}
                  onClick={() => onCloseSurface(surface)}
                >
                  x
                </button>
              </div>
            );
          })}
          {items.length > 0 ? <SurfaceAddMenu onAddSurface={onAddSurface} /> : null}
        </div>
      </div>
      <div className="right-panel-body">
        {activeSurface ? children : <RightPanelEmptyState onAddSurface={onAddSurface} />}
      </div>
    </aside>
  );
}
