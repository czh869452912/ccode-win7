import React from "react";
import { createPortal } from "react-dom";

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function menuPosition(anchor, menu) {
  const viewportWidth = window.innerWidth || 1024;
  const viewportHeight = window.innerHeight || 768;
  const anchorRect = anchor.getBoundingClientRect();
  const menuWidth = menu?.offsetWidth || 176;
  const menuHeight = menu?.offsetHeight || 220;
  const left = clamp(anchorRect.left, 8, Math.max(8, viewportWidth - menuWidth - 8));
  const below = anchorRect.bottom + 6;
  const above = anchorRect.top - menuHeight - 6;
  const top =
    below + menuHeight <= viewportHeight - 8
      ? below
      : clamp(above, 8, viewportHeight - menuHeight - 8);
  return { left: Math.round(left), top: Math.round(top) };
}

export default function FloatingMenu({
  open,
  anchorRef,
  onClose,
  className = "",
  children,
  role = "menu",
}) {
  const menuRef = React.useRef(null);
  const [position, setPosition] = React.useState({ left: 0, top: 0 });

  React.useLayoutEffect(() => {
    if (!open) return undefined;
    const anchor = anchorRef && anchorRef.current;
    const menu = menuRef.current;
    if (!anchor || !menu) return undefined;

    function updatePosition() {
      setPosition(menuPosition(anchor, menu));
    }

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [anchorRef, open]);

  React.useEffect(() => {
    if (!open) return undefined;
    function onPointerDown(event) {
      const anchor = anchorRef && anchorRef.current;
      const menu = menuRef.current;
      if (menu && menu.contains(event.target)) return;
      if (anchor && anchor.contains(event.target)) return;
      onClose && onClose();
    }
    function onKeyDown(event) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose && onClose();
      }
    }
    document.addEventListener("pointerdown", onPointerDown, true);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown, true);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [anchorRef, onClose, open]);

  if (!open || typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={menuRef}
      className={`floating-menu-layer ${className}`.trim()}
      role={role}
      style={{ left: `${position.left}px`, top: `${position.top}px` }}
    >
      {children}
    </div>,
    document.body,
  );
}
