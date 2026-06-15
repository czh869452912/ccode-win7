export function shouldReconnectSocket({ activeToken, socketToken, manualClose }) {
  if (manualClose) return false;
  if (!socketToken) return false;
  return activeToken === socketToken;
}
