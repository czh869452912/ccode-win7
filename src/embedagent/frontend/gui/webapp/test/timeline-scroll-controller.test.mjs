import assert from "node:assert/strict";

import { createTimelineScrollController } from "../src/app-runtime/timeline-scroll-controller.js";

function createElement({
  scrollHeight = 1000,
  scrollTop = 900,
  clientHeight = 100,
} = {}) {
  return {
    scrollHeight,
    scrollTop,
    clientHeight,
  };
}

export function runTimelineScrollControllerTests() {
  let element = createElement({ scrollHeight: 1200, scrollTop: 500, clientHeight: 300 });
  const controller = createTimelineScrollController({
    getElement: () => element,
    bottomThreshold: 80,
  });

  controller.syncToBottom();
  assert.equal(element.scrollTop, 1200);

  element.scrollTop = 700;
  assert.equal(controller.handleScroll(), false);
  controller.syncToBottom();
  assert.equal(element.scrollTop, 700);
  assert.equal(controller.markFollowingBottom(), true);
  controller.syncToBottom();
  assert.equal(element.scrollTop, 1200);

  element.scrollTop = 830;
  assert.equal(controller.handleScroll(), true);
  controller.syncToBottom();
  assert.equal(element.scrollTop, 1200);

  element = null;
  assert.equal(controller.handleScroll(), false);
  assert.equal(controller.syncToBottom(), false);
}
