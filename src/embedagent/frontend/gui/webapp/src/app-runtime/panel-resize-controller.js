const RESIZE_DIRECTIONS = Object.freeze({
  RIGHT: 1,
  LEFT: -1,
});

function defaultStartValue(cssVar) {
  return cssVar === "--sidebar-w-raw" ? 220 : 260;
}

function clampPanelWidth(value) {
  return Math.max(160, Math.min(480, value));
}

function readStartValue(documentObject, getComputedStyleFn, cssVar) {
  const documentElement = documentObject?.documentElement;
  const styleReader =
    typeof getComputedStyleFn === "function" && documentElement
      ? getComputedStyleFn(documentElement)
      : null;
  const current = parseFloat(String(styleReader?.getPropertyValue(cssVar) || "").trim());
  return Number.isFinite(current) && current > 0 ? current : defaultStartValue(cssVar);
}

export function createPanelResizeController({ documentObject, getComputedStyleFn } = {}) {
  const documentRef =
    documentObject || (typeof document !== "undefined" ? document : { documentElement: null });
  const readComputedStyle =
    getComputedStyleFn || (typeof getComputedStyle === "function" ? getComputedStyle : null);

  function startResize(event, cssVar, direction) {
    if (!event?.currentTarget) return;
    event.preventDefault();
    const handle = event.currentTarget;
    handle.classList.add("dragging");
    const startX = event.clientX;
    const startVal = readStartValue(documentRef, readComputedStyle, cssVar);

    function onMove(moveEvent) {
      const delta = (moveEvent.clientX - startX) * direction;
      const newVal = clampPanelWidth(startVal + delta);
      documentRef.documentElement.style.setProperty(cssVar, `${newVal}px`);
    }

    function onEnd() {
      handle.classList.remove("dragging");
      handle.removeEventListener("pointermove", onMove);
      handle.removeEventListener("pointerup", onEnd);
      handle.removeEventListener("pointercancel", onEnd);
    }

    handle.setPointerCapture(event.pointerId);
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onEnd);
    handle.addEventListener("pointercancel", onEnd);
  }

  function startSidebarResize(event) {
    startResize(event, "--sidebar-w-raw", RESIZE_DIRECTIONS.RIGHT);
  }

  function startRightPanelResize(event) {
    startResize(event, "--right-panel-w-raw", RESIZE_DIRECTIONS.LEFT);
  }

  return { startRightPanelResize, startSidebarResize };
}
