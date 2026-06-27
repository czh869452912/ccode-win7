import React from "react";
import {
  rightPanelLauncherSurfaceDefinitions,
  surfaceDefinitionFor,
  titleForSurfaceKind,
} from "../../workbench/surfaces.js";
import FloatingMenu from "./FloatingMenu.jsx";

const SURFACE_TAB_TEST_IDS = {
  preview: "right-panel-surface-tab--preview",
  file: "right-panel-surface-tab--file",
};

function surfaceTitle(surface) {
  if (!surface) return "";
  if (surface.title) return surface.title;
  return titleForSurfaceKind(surface.kind);
}

function SurfaceIcon({ kind }) {
  const definition = surfaceDefinitionFor(kind);
  return <span className="right-panel-surface-icon" aria-hidden="true">{definition?.icon || "S"}</span>;
}

function SurfaceTabMenu({
  surface,
  onCloseSurface,
  onCloseOtherSurfaces,
  onCloseSurfacesToRight,
  onCloseAllSurfaces,
}) {
  const [open, setOpen] = React.useState(false);
  const buttonRef = React.useRef(null);
  return (
    <span className="right-panel-tab-menu">
      <button
        ref={buttonRef}
        type="button"
        className="right-panel-tab-menu-button"
        aria-label={`Surface actions for ${surfaceTitle(surface)}`}
        aria-expanded={open}
        onClick={(event) => {
          event.stopPropagation();
          setOpen((value) => !value);
        }}
      >
        ...
      </button>
      <FloatingMenu
        open={open}
        anchorRef={buttonRef}
        onClose={() => setOpen(false)}
        className="right-panel-tab-menu-popup"
      >
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            setOpen(false);
            onCloseSurface(surface);
          }}
        >
          Close
        </button>
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
      </FloatingMenu>
    </span>
  );
}

function SurfaceAddMenu({ onAddSurface }) {
  const [open, setOpen] = React.useState(false);
  const buttonRef = React.useRef(null);
  const availableSurfaces = rightPanelLauncherSurfaceDefinitions();
  return (
    <span className="right-panel-add-menu">
      <button
        ref={buttonRef}
        type="button"
        className="right-panel-add-surface"
        aria-label="Add panel surface"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title="Add panel surface"
      >
        +
      </button>
      <FloatingMenu
        open={open}
        anchorRef={buttonRef}
        onClose={() => setOpen(false)}
        className="right-panel-add-menu-popup"
      >
        {availableSurfaces.map((definition) => {
          return (
            <button
              key={definition.kind}
              type="button"
              role="menuitem"
              onClick={() => {
                setOpen(false);
                onAddSurface(definition.kind);
              }}
            >
              <SurfaceIcon kind={definition.kind} />
              <span>{definition.title}</span>
            </button>
          );
        })}
      </FloatingMenu>
    </span>
  );
}

function RightPanelEmptyState({ onAddSurface }) {
  const availableSurfaces = rightPanelLauncherSurfaceDefinitions();
  return (
    <div className="right-panel-empty-state" data-testid="right-panel-empty-state">
      <div className="right-panel-empty-copy">
        <h3>Open a surface</h3>
        <p>Choose what to show in the right panel.</p>
      </div>
      <div className="right-panel-empty-grid">
        {availableSurfaces.map((definition) => {
          return (
            <button
              key={definition.kind}
              type="button"
              className="right-panel-empty-card"
              onClick={() => onAddSurface(definition.kind)}
              data-testid={`right-panel-empty-surface--${definition.kind}`}
            >
              <SurfaceIcon kind={definition.kind} />
              <span>{definition.title}</span>
              <small>{definition.description}</small>
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
          <div className="right-panel-tab-strip">
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
                    onCloseSurface={onCloseSurface}
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
      </div>
      <div className="right-panel-body">
        {activeSurface ? children : <RightPanelEmptyState onAddSurface={onAddSurface} />}
      </div>
    </aside>
  );
}
