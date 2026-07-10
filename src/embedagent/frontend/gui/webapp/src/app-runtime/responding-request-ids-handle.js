function normalizeRequestIds(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => String(item || "")).filter(Boolean);
}

export function createRespondingRequestIdsHandle({
  initialRequestIds,
  setRequestIds,
} = {}) {
  let currentRequestIds = normalizeRequestIds(initialRequestIds);
  const writeRequestIds = typeof setRequestIds === "function" ? setRequestIds : () => {};

  function read() {
    return currentRequestIds;
  }

  function sync(value) {
    currentRequestIds = normalizeRequestIds(value);
    return currentRequestIds;
  }

  function set(value) {
    const nextValue = typeof value === "function" ? value(currentRequestIds) : value;
    currentRequestIds = normalizeRequestIds(nextValue);
    writeRequestIds(currentRequestIds);
    return currentRequestIds;
  }

  return { read, set, sync };
}
