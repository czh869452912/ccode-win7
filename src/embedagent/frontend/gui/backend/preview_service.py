from __future__ import annotations

import os
import re
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from html.parser import HTMLParser
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

PREVIEW_PROBE_TIMEOUT_SEC = 2.0
PREVIEW_URL_MAX_LENGTH = 2048
PREVIEW_TAB_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        HTMLParser.__init__(self)
        self._in_title = False
        self.title = ""

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if str(tag or "").lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if str(tag or "").lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = str(data or "").strip()


def normalize_preview_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("preview_url_required")
    if len(text) > PREVIEW_URL_MAX_LENGTH:
        raise ValueError("preview_url_too_long")
    if "://" not in text:
        text = "http://%s" % text
    parsed = urlparse(text)
    if parsed.scheme != "http":
        raise ValueError("preview_url_not_local")
    host = (parsed.hostname or "").lower()
    if host not in LOCAL_HOSTS:
        raise ValueError("preview_url_not_local")
    if not parsed.port:
        raise ValueError("preview_url_not_local")
    return text


def default_probe_runner(url: str, timeout_sec: float) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "EmbedAgent-Preview/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            status_code = int(getattr(response, "status", 0) or 0)
            content_type = str(response.headers.get("content-type") or "")
            title = ""
            if "text/html" in content_type.lower():
                body = response.read(65536).decode("utf-8", "replace")
                parser = _TitleParser()
                parser.feed(body)
                title = parser.title
            return {
                "reachable": True,
                "status_code": status_code,
                "title": title,
                "error": "",
            }
    except urllib.error.HTTPError as exc:
        return {
            "reachable": 400 <= int(exc.code or 0) < 600,
            "status_code": int(exc.code or 0),
            "title": "",
            "error": str(getattr(exc, "reason", "") or exc),
        }
    except (OSError, ValueError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", None)
        return {
            "reachable": False,
            "status_code": 0,
            "title": "",
            "error": str(reason or exc or "connection failed"),
        }


def default_external_opener(url: str) -> bool:
    return bool(webbrowser.open(url, new=2, autoraise=True))


class PreviewService(object):
    def __init__(
        self,
        workspace_root: str,
        probe_runner: Optional[Callable[[str, float], Dict[str, Any]]] = None,
        external_opener: Optional[Callable[[str], bool]] = None,
        probe_timeout_sec: float = PREVIEW_PROBE_TIMEOUT_SEC,
    ) -> None:
        self.workspace_root = os.path.realpath(workspace_root)
        self.probe_runner = probe_runner or default_probe_runner
        self.external_opener = external_opener or default_external_opener
        self.probe_timeout_sec = max(0.1, float(probe_timeout_sec or PREVIEW_PROBE_TIMEOUT_SEC))
        self._lock = threading.RLock()
        self._sessions = {}  # type: Dict[str, Dict[str, Dict[str, Any]]]
        self._active_tab_ids = {}  # type: Dict[str, str]
        self._next_tab = 1

    def list_sessions(self, thread_id: str) -> Dict[str, Any]:
        normalized_thread_id = self._normalize_thread_id(thread_id)
        with self._lock:
            sessions = list(self._sessions.get(normalized_thread_id, {}).values())
            sessions.sort(key=lambda item: item.get("updated_at", ""))
            active_tab_id = self._active_tab_ids.get(normalized_thread_id, "")
            return {
                "thread_id": normalized_thread_id,
                "active_tab_id": active_tab_id,
                "sessions": [dict(item) for item in sessions],
            }

    def open(self, thread_id: str, url: str = "") -> Dict[str, Any]:
        normalized_thread_id = self._normalize_thread_id(thread_id)
        normalized_url = normalize_preview_url(url) if str(url or "").strip() else ""
        with self._lock:
            tab_id = self._new_tab_id_locked()
            snapshot = self._snapshot(
                normalized_thread_id,
                tab_id,
                normalized_url,
                "idle" if not normalized_url else "loading",
                title="",
                error_code=0,
                error_description="",
            )
            self._sessions.setdefault(normalized_thread_id, {})[tab_id] = snapshot
            self._active_tab_ids[normalized_thread_id] = tab_id
        if normalized_url:
            return self.refresh(normalized_thread_id, tab_id)
        return snapshot

    def refresh(self, thread_id: str, tab_id: str) -> Dict[str, Any]:
        normalized_thread_id = self._normalize_thread_id(thread_id)
        normalized_tab_id = self._normalize_tab_id(tab_id)
        with self._lock:
            existing = self._require_locked(normalized_thread_id, normalized_tab_id)
            url = str(existing.get("url") or "")
            if not url:
                return dict(existing)
            loading = self._snapshot(
                normalized_thread_id,
                normalized_tab_id,
                url,
                "loading",
                title=str(existing.get("title") or ""),
                error_code=0,
                error_description="",
            )
            self._sessions[normalized_thread_id][normalized_tab_id] = loading
        result = self.probe_runner(url, self.probe_timeout_sec) or {}
        reachable = bool(result.get("reachable"))
        status_code = int(result.get("status_code") or 0)
        title = str(result.get("title") or "")
        error = str(result.get("error") or "")
        status = "success" if reachable else "failed"
        if not reachable and not error:
            error = "connection failed"
        with self._lock:
            snapshot = self._snapshot(
                normalized_thread_id,
                normalized_tab_id,
                url,
                status,
                title=title,
                error_code=0 if reachable else status_code or -1,
                error_description=error,
            )
            self._sessions[normalized_thread_id][normalized_tab_id] = snapshot
            self._active_tab_ids[normalized_thread_id] = normalized_tab_id
            return dict(snapshot)

    def close(self, thread_id: str, tab_id: str) -> Dict[str, Any]:
        normalized_thread_id = self._normalize_thread_id(thread_id)
        normalized_tab_id = self._normalize_tab_id(tab_id)
        with self._lock:
            self._require_locked(normalized_thread_id, normalized_tab_id)
            self._sessions.get(normalized_thread_id, {}).pop(normalized_tab_id, None)
            if self._active_tab_ids.get(normalized_thread_id) == normalized_tab_id:
                remaining = self._sessions.get(normalized_thread_id, {})
                self._active_tab_ids[normalized_thread_id] = next(iter(remaining.keys()), "")
            return {
                "thread_id": normalized_thread_id,
                "tab_id": normalized_tab_id,
                "status": "closed",
                "updated_at": _utc_now(),
            }

    def open_external(self, url: str) -> Dict[str, Any]:
        normalized_url = normalize_preview_url(url)
        opened = bool(self.external_opener(normalized_url))
        return {
            "url": normalized_url,
            "opened": opened,
            "updated_at": _utc_now(),
        }

    def _snapshot(
        self,
        thread_id: str,
        tab_id: str,
        url: str,
        status: str,
        title: str,
        error_code: int,
        error_description: str,
    ) -> Dict[str, Any]:
        return {
            "thread_id": thread_id,
            "tab_id": tab_id,
            "url": url,
            "status": status,
            "title": title,
            "can_go_back": False,
            "can_go_forward": False,
            "error_code": int(error_code or 0),
            "error_description": str(error_description or ""),
            "updated_at": _utc_now(),
        }

    def _new_tab_id_locked(self) -> str:
        value = "preview-%d" % self._next_tab
        self._next_tab += 1
        return value

    def _require_locked(self, thread_id: str, tab_id: str) -> Dict[str, Any]:
        state = self._sessions.get(thread_id, {}).get(tab_id)
        if state is None:
            raise ValueError("preview_tab_not_found")
        return state

    def _normalize_thread_id(self, thread_id: str) -> str:
        value = str(thread_id or "").strip()
        if not value:
            raise ValueError("invalid_session_id")
        return value

    def _normalize_tab_id(self, tab_id: str) -> str:
        value = str(tab_id or "").strip()
        if not PREVIEW_TAB_ID_RE.match(value):
            raise ValueError("invalid_preview_tab_id")
        return value
