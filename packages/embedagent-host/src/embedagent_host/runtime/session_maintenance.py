from __future__ import annotations

import logging
import threading

_LOG = logging.getLogger(__name__)


class HostedSessionMaintenance(object):
    def __init__(
        self,
        summary_store,
        project_memory_store,
        memory_maintenance,
        maintenance_interval=4,
    ):
        self.summary_store = summary_store
        self.project_memory_store = project_memory_store
        self.memory_maintenance = memory_maintenance
        self.maintenance_interval = max(1, int(maintenance_interval or 1))
        self._counter = 0
        self._lock = threading.Lock()

    def refresh(self, session, current_mode, assembly=None):
        summary_ref = None
        try:
            summary_ref = self.summary_store.persist(session, current_mode, assembly)
        except (OSError, TypeError, ValueError) as exc:
            _LOG.warning("session summary persist failed: %s", exc)
        try:
            self.project_memory_store.refresh(session, current_mode, summary_ref)
        except (OSError, TypeError, ValueError) as exc:
            _LOG.warning("project memory refresh failed: %s", exc)
        with self._lock:
            self._counter += 1
            if self._counter < self.maintenance_interval:
                return
            self._counter = 0
        try:
            self.memory_maintenance.run()
        except (RuntimeError, TypeError, ValueError) as exc:
            _LOG.warning("memory maintenance failed: %s", exc)
