import React from "react";
import {
  rightPanelLauncherSurfaceDefinitions,
  surfaceChromeLabels,
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

function joinLabel(prefix, value) {
  const left = String(prefix || "").trim();
  const right = String(value || "").trim();
  return left && right ? `${left} ${right}` : left || right;
}

function SurfaceIcon({ kind, definition = null, appCapabilities = null, chrome = null }) {
  const resolved = definition || surfaceDefinitionFor(kind, appCapabilities);
  const labels = chrome || surfaceChromeLabels(appCapabilities);
  return (
    <span className="right-panel-surface-icon" aria-hidden="true">
      {resolved?.icon || labels.defaultIcon}
    </span>
  );
}

function SurfaceTabMenu({
  chrome,
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
        aria-label={joinLabel(chrome.surfaceActionsLabelPrefix, surfaceTitle(surface))}
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
          {chrome.closeActionLabel}
        </button>
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            setOpen(false);
            onCloseOtherSurfaces(surface);
          }}
        >
          {chrome.closeOthersActionLabel}
        </button>
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            setOpen(false);
            onCloseSurfacesToRight(surface);
          }}
        >
          {chrome.closeToRightActionLabel}
        </button>
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            setOpen(false);
            onCloseAllSurfaces();
          }}
        >
          {chrome.closeAllActionLabel}
        </button>
      </FloatingMenu>
    </span>
  );
}

function SurfaceAddMenu({ appCapabilities, onAddSurface }) {
  const [open, setOpen] = React.useState(false);
  const buttonRef = React.useRef(null);
  const availableSurfaces = rightPanelLauncherSurfaceDefinitions(appCapabilities);
  const chrome = surfaceChromeLabels(appCapabilities);
  if (availableSurfaces.length === 0) return null;
  return (
    <span className="right-panel-add-menu">
      <button
        ref={buttonRef}
        type="button"
        className="right-panel-add-surface"
        aria-label={chrome.addSurfaceLabel}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        title={chrome.addSurfaceLabel}
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
              <SurfaceIcon definition={definition} chrome={chrome} />
              <span>{definition.title}</span>
            </button>
          );
        })}
      </FloatingMenu>
    </span>
  );
}

function RightPanelEmptyState({ appCapabilities, onAddSurface }) {
  const availableSurfaces = rightPanelLauncherSurfaceDefinitions(appCapabilities);
  const chrome = surfaceChromeLabels(appCapabilities);
  return (
    <div className="right-panel-empty-state" data-testid="right-panel-empty-state">
      <div className="right-panel-empty-copy">
        <h3>{chrome.emptyTitle}</h3>
        <p>{chrome.emptyBody}</p>
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
              <SurfaceIcon definition={definition} chrome={chrome} />
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
  appCapabilities,
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
  const chrome = surfaceChromeLabels(appCapabilities);
  const tabListRef = React.useRef(null);
  React.useEffect(() => {
    const activeTab = tabListRef.current?.querySelector("[data-active-tab='true']");
    activeTab?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [activeSurfaceId]);

  return (
    <aside
      className="right-panel"
      role="complementary"
      aria-label={chrome.rightPanelAriaLabel}
      data-testid="right-panel"
    >
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
                    <SurfaceIcon
                      kind={surface.kind}
                      appCapabilities={appCapabilities}
                      chrome={chrome}
                    />
                    <span>{title}</span>
                  </button>
                  <SurfaceTabMenu
                    chrome={chrome}
                    surface={surface}
                    onCloseSurface={onCloseSurface}
                    onCloseOtherSurfaces={onCloseOtherSurfaces}
                    onCloseSurfacesToRight={onCloseSurfacesToRight}
                    onCloseAllSurfaces={onCloseAllSurfaces}
                  />
                  <button
                    type="button"
                    className="right-panel-tab-close"
                    aria-label={joinLabel(chrome.closeLabelPrefix, title)}
                    onClick={() => onCloseSurface(surface)}
                  >
                    x
                  </button>
                </div>
              );
            })}
            {items.length > 0 ? (
              <SurfaceAddMenu appCapabilities={appCapabilities} onAddSurface={onAddSurface} />
            ) : null}
          </div>
        </div>
      </div>
      <div className="right-panel-body">
        {activeSurface ? children : (
          <RightPanelEmptyState appCapabilities={appCapabilities} onAddSurface={onAddSurface} />
        )}
      </div>
    </aside>
  );
}
