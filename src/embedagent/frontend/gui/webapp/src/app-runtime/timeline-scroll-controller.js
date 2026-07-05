export function createTimelineScrollController({
  getElement,
  bottomThreshold = 80,
} = {}) {
  let followBottom = true;
  const readElement = typeof getElement === "function" ? getElement : () => null;

  function syncToBottom() {
    const element = readElement();
    if (!element || !followBottom) return false;
    element.scrollTop = element.scrollHeight;
    return true;
  }

  function handleScroll() {
    const element = readElement();
    if (!element) {
      followBottom = false;
      return false;
    }
    followBottom =
      element.scrollHeight - element.scrollTop - element.clientHeight < bottomThreshold;
    return followBottom;
  }

  function markFollowingBottom() {
    followBottom = true;
    return followBottom;
  }

  function isFollowingBottom() {
    return followBottom;
  }

  return { handleScroll, isFollowingBottom, markFollowingBottom, syncToBottom };
}
