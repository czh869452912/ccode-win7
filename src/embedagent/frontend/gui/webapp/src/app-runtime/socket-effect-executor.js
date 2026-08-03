function isReloadRequired(transportState) {
  return (
    transportState?.reloadState === "reload_required" ||
    transportState?.reloadState === "degraded"
  );
}

export function createSocketEffectExecutor({
  dispatch,
  executeLoaderRequest,
  getSessionTransportController,
  getCurrentSessionId,
  clearRespondingRequestId,
} = {}) {
  const send = typeof dispatch === "function" ? dispatch : () => {};
  const executeLoader =
    typeof executeLoaderRequest === "function" ? executeLoaderRequest : () => {};
  const readTransportController =
    typeof getSessionTransportController === "function"
      ? getSessionTransportController
      : () => null;
  const readCurrentSessionId =
    typeof getCurrentSessionId === "function" ? getCurrentSessionId : () => "";

  function applyTransportEvent(transportController, entry) {
    if (transportController && typeof transportController.applyEvent === "function") {
      return transportController.applyEvent(entry || {});
    }
    return { state: null, accepted: false, reason: "transport_unavailable" };
  }

  function recoverIfNeeded(transportController, nextTransport) {
    const currentSessionId = readCurrentSessionId();
    if (!isReloadRequired(nextTransport) || !currentSessionId) return;
    if (transportController && typeof transportController.recover === "function") {
      void transportController.recover(currentSessionId);
    }
  }

  return function executeSocketEffects(effects = {}) {
    const transportEvents = Array.isArray(effects.transportEvents)
      ? effects.transportEvents
      : [];
    let transportAccepted = true;
    if (transportEvents.length) {
      const transportController = readTransportController();
      let nextTransport = null;
      for (const entry of transportEvents) {
        const result = applyTransportEvent(transportController, entry);
        nextTransport = result?.state || nextTransport;
        if (!result?.accepted) transportAccepted = false;
      }
      recoverIfNeeded(transportController, nextTransport);
    }
    if (!transportAccepted) return;

    for (const action of effects.actions || []) {
      if (
        action?.type === "interaction_resolved" &&
        typeof clearRespondingRequestId === "function"
      ) {
        clearRespondingRequestId(action.requestId);
      }
      send(action);
    }

    for (const request of effects.loaderRequests || []) {
      void executeLoader(request);
    }
  };
}
