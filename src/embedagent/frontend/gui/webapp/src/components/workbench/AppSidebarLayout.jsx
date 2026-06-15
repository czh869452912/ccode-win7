import React from "react";

export default function AppSidebarLayout({
  header,
  sidebar,
  main,
  rightPanel,
  bottomDrawer,
  rightPanelOpen,
  bottomDrawerOpen,
  onResizeSidebar,
  onResizeRightPanel,
}) {
  return (
    <div
      className={`workbench-layout${rightPanelOpen ? " right-open" : " right-closed"}${
        bottomDrawerOpen ? " drawer-open" : ""
      }`}
      data-testid="workbench-layout"
    >
      <div className="workbench-header-slot">{header}</div>
      <div className="workbench-body">
        <div className="workbench-sidebar-slot">{sidebar}</div>
        <div
          className="resize-handle sidebar-resize-handle"
          onPointerDown={onResizeSidebar}
          aria-hidden="true"
        />
        <div className="workbench-center">
          <div className="workbench-main-slot">{main}</div>
          {bottomDrawerOpen ? (
            <div className="workbench-bottom-slot">{bottomDrawer}</div>
          ) : null}
        </div>
        <div
          className="resize-handle right-resize-handle"
          onPointerDown={onResizeRightPanel}
          aria-hidden="true"
        />
        {rightPanelOpen ? (
          <div className="workbench-right-slot">{rightPanel}</div>
        ) : (
          <div className="workbench-right-collapsed" aria-hidden="true" />
        )}
      </div>
    </div>
  );
}
