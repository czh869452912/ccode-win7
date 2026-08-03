export function shouldReconnectSocket({ activeToken, socketToken, manualClose, closed = false }) {
  if (closed || manualClose) return false;
  if (!socketToken) return false;
  return activeToken === socketToken;
}
