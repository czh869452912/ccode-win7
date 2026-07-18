const SENSITIVE_KEY_PARTS = ["api_key", "authorization", "password", "secret", "token"];
const BLOCKED_KEYS = new Set(["prompt", "transcript", "tool_output"]);

function objectValue(value) {
  return value && typeof value === "object" && !Array.isArray(value) ? value : {};
}

function isJsonSafe(value) {
  if (value === null || typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return true;
  }
  if (Array.isArray(value)) return value.every(isJsonSafe);
  if (value && typeof value === "object") {
    return Object.entries(value).every(([key, item]) => typeof key === "string" && isJsonSafe(item));
  }
  return false;
}

function containsSensitiveKey(value) {
  if (Array.isArray(value)) return value.some(containsSensitiveKey);
  if (!value || typeof value !== "object") return false;
  return Object.entries(value).some(([key, item]) => {
    const lowered = key.toLowerCase();
    return BLOCKED_KEYS.has(lowered)
      || SENSITIVE_KEY_PARTS.some((part) => lowered.includes(part))
      || containsSensitiveKey(item);
  });
}

export function normalizeProtocolEnvelope(input = {}, expectedProtocol = "") {
  const data = objectValue(input);
  const errors = [];
  const protocol = typeof data.protocol === "string" ? data.protocol.trim() : "";
  const sequence = data.sequence;
  const revision = typeof data.revision === "string" ? data.revision.trim() : "";
  const payload = objectValue(data.payload);
  if (!protocol || (expectedProtocol && protocol !== expectedProtocol)) errors.push("protocol");
  if (data.version !== 1) errors.push("version");
  if (!Number.isInteger(sequence) || sequence < 0) errors.push("sequence");
  if (!revision) errors.push("revision");
  if (!isJsonSafe(payload)) errors.push("payload");
  else if (containsSensitiveKey(payload)) errors.push("sensitive");
  return {
    valid: errors.length === 0,
    errors,
    protocol,
    version: data.version,
    sequence,
    revision,
    payload,
  };
}

export function protocolEnvelopeIsValid(value) {
  return Boolean(value && value.valid === true && Array.isArray(value.errors) && value.errors.length === 0);
}
