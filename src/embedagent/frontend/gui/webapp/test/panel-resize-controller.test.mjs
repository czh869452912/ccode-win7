import assert from "node:assert/strict";

import {
  createPanelResizeController,
  RESIZE_DIRECTIONS,
} from "../src/app-runtime/panel-resize-controller.js";

function createHandle() {
  const listeners = {};
  const classes = new Set();
  return {
    listeners,
    classList: {
      add(value) {
        classes.add(value);
      },
      remove(value) {
        classes.delete(value);
      },
      has(value) {
        return classes.has(value);
      },
    },
    setPointerCapture(pointerId) {
      this.pointerId = pointerId;
    },
    addEventListener(name, callback) {
      listeners[name] = callback;
    },
    removeEventListener(name, callback) {
      if (listeners[name] === callback) delete listeners[name];
    },
  };
}

export function runPanelResizeControllerTests() {
  const styleWrites = [];
  const documentObject = {
    documentElement: {
      style: {
        setProperty(name, value) {
          styleWrites.push([name, value]);
        },
      },
    },
  };
  const controller = createPanelResizeController({
    documentObject,
    getComputedStyleFn: () => ({
      getPropertyValue: () => "220",
    }),
  });
  const handle = createHandle();
  let prevented = false;

  controller.startResize(
    {
      preventDefault() {
        prevented = true;
      },
      currentTarget: handle,
      clientX: 100,
      pointerId: 7,
    },
    "--sidebar-w-raw",
    RESIZE_DIRECTIONS.RIGHT,
  );

  assert.equal(prevented, true);
  assert.equal(handle.pointerId, 7);
  assert.equal(handle.classList.has("dragging"), true);

  handle.listeners.pointermove({ clientX: 130 });
  assert.deepEqual(styleWrites[0], ["--sidebar-w-raw", "250px"]);

  handle.listeners.pointermove({ clientX: -500 });
  assert.deepEqual(styleWrites[1], ["--sidebar-w-raw", "160px"]);

  handle.listeners.pointerup();
  assert.equal(handle.classList.has("dragging"), false);
  assert.equal(handle.listeners.pointermove, undefined);
  assert.equal(handle.listeners.pointerup, undefined);
  assert.equal(handle.listeners.pointercancel, undefined);

  const rightHandle = createHandle();
  controller.startResize(
    {
      preventDefault() {},
      currentTarget: rightHandle,
      clientX: 100,
      pointerId: 8,
    },
    "--right-panel-w-raw",
    RESIZE_DIRECTIONS.LEFT,
  );
  rightHandle.listeners.pointermove({ clientX: 60 });
  assert.deepEqual(styleWrites[2], ["--right-panel-w-raw", "260px"]);
}
