export function createSocketEffectExecutor({
  dispatch,
  executeLoaderRequest,
  clearRespondingRequestId,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const executeLoader =
    typeof executeLoaderRequest === "function" ? executeLoaderRequest : () => {};

  return function executeSocketEffects(effects = {}) {
    for (const action of effects.actions || []) {
      if (
        action?.type === "interaction_resolved" &&
        typeof clearRespondingRequestId === "function"
      ) {
        clearRespondingRequestId(action.requestId);
      }
      send(action);
    }
    for (const request of effects.loaderRequests || []) void executeLoader(request);
  };
}
