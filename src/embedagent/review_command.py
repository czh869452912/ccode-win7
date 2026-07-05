from __future__ import annotations

from typing import Any, Dict, List, Optional

from embedagent.tool_evidence import (
    is_quality_gate_data,
    recipe_action_from_data,
)


class ReviewCommandService(object):
    """Builds the hosted /review command payload from recent tool evidence."""

    def __init__(self, tools: Any) -> None:
        self.tools = tools

    def build_payload_from_session(self, session: Any, limit: int = 400) -> Dict[str, Any]:
        return self.build_payload(self._events_from_session(session, limit=limit))

    def build_payload(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        findings = []  # type: List[Dict[str, Any]]
        saw_verify = False
        saw_tests = False
        sections = {
            "diagnostics": [],
            "tests": [],
            "coverage": [],
            "quality": [],
            "git": [],
        }  # type: Dict[str, List[Dict[str, Any]]]
        for record in events:
            if record.get("event") != "tool_finished":
                continue
            payload = record.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            tool_name = str(payload.get("tool_name") or "")
            success = bool(payload.get("success"))
            data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
            review_kind = self._review_kind(tool_name, data)
            if review_kind in ("build", "diagnostic", "test", "coverage", "quality"):
                saw_verify = True
            if review_kind == "test":
                saw_tests = True
            self._append_review_section(sections, tool_name, success, payload, data)
            finding = self._review_finding_from_tool(tool_name, success, payload, data)
            if finding is not None:
                findings.append(finding)

        diff_observation = self.tools.execute("git_diff", {"path": ".", "scope": "working"})
        diff_data = diff_observation.data if isinstance(diff_observation.data, dict) else {}
        diff_file_count = int(diff_data.get("file_count") or 0)
        sections["git"].append(
            {
                "kind": "git_diff",
                "available": bool(diff_observation.success),
                "error": diff_observation.error or "",
                "file_count": diff_file_count,
                "line_count": int(diff_data.get("line_count") or 0),
                "diff_preview": str(diff_data.get("diff") or ""),
                "diff_stored_path": str(diff_data.get("diff_stored_path") or ""),
                "diff_char_count": int(diff_data.get("diff_char_count") or 0),
            }
        )
        if diff_observation.success and diff_file_count > 0 and not saw_verify:
            findings.append(
                {
                    "id": "verify-missing",
                    "priority": 2,
                    "severity": "medium",
                    "title": "Missing verification evidence",
                    "body": "工作区存在 %s 个改动文件，但最近没有看到完整 verify 证据。"
                    % diff_file_count,
                    "evidence": [
                        {"type": "git_diff", "file_count": diff_file_count},
                    ],
                }
            )
        if saw_verify and not saw_tests:
            findings.append(
                {
                    "id": "tests-missing",
                    "priority": 2,
                    "severity": "medium",
                    "title": "No recent test execution",
                    "body": "最近的验证证据里没有测试 recipe 结果，测试覆盖存在缺口。",
                    "evidence": [
                        {
                            "type": "verify_gap",
                            "evidence_kind": "recipe_action",
                            "recipe_action": "test",
                        }
                    ],
                }
            )
        findings.sort(
            key=lambda item: (int(item.get("priority") or 99), str(item.get("title") or ""))
        )
        no_findings = not findings
        residual_risks = []
        if no_findings:
            residual_risks.append("需要在真实工程和 Win7 目标环境上再次执行完整 verify。")
        elif not saw_verify:
            residual_risks.append("当前结论缺少完整 verify 证据，只能视为阶段性审查。")
        return {
            "summary": "发现 %s 条问题。" % len(findings) if findings else "未发现明确阻塞项。",
            "findings": findings,
            "residual_risks": residual_risks,
            "no_findings": no_findings,
            "diff_file_count": diff_file_count,
            "verify_evidence_present": saw_verify,
            "tests_seen": saw_tests,
            "sections": sections,
        }

    def _events_from_session(self, session: Any, limit: int = 400) -> List[Dict[str, Any]]:
        events = []  # type: List[Dict[str, Any]]
        seen_call_ids = set()
        for turn in list(getattr(session, "turns", []) or []):
            for step in list(getattr(turn, "steps", []) or []):
                for record in list(getattr(step, "tool_calls", []) or []):
                    observation = getattr(record, "observation", None)
                    if observation is None:
                        continue
                    call_id = str(getattr(record, "call_id", "") or "")
                    if call_id and call_id in seen_call_ids:
                        continue
                    if call_id:
                        seen_call_ids.add(call_id)
                    data = (
                        observation.data
                        if isinstance(getattr(observation, "data", None), dict)
                        else {}
                    )
                    events.append(
                        {
                            "event": "tool_finished",
                            "payload": {
                                "tool_name": getattr(record, "tool_name", ""),
                                "success": bool(getattr(observation, "success", False)),
                                "call_id": call_id,
                                "error": getattr(observation, "error", "") or "",
                                "data": dict(data),
                            },
                        }
                    )
        if limit > 0:
            return events[-limit:]
        return events

    def markdown_lines(self, review: Dict[str, Any]) -> List[str]:
        lines = ["## Review Findings", ""]
        findings = review.get("findings") if isinstance(review.get("findings"), list) else []
        if findings:
            for item in findings:
                lines.append(
                    "- [%s/P%s] **%s**: %s"
                    % (
                        str(item.get("severity") or "info"),
                        str(item.get("priority") or "-"),
                        str(item.get("title") or "Finding"),
                        str(item.get("body") or ""),
                    )
                )
        else:
            lines.append("- 未发现明确阻塞项。")
        residual = (
            review.get("residual_risks") if isinstance(review.get("residual_risks"), list) else []
        )
        if residual:
            lines.extend(["", "## Residual Risks", ""])
            for item in residual:
                lines.append("- %s" % str(item or ""))
        return lines

    def _append_review_section(
        self,
        sections: Dict[str, List[Dict[str, Any]]],
        tool_name: str,
        success: bool,
        payload: Dict[str, Any],
        data: Dict[str, Any],
    ) -> None:
        review_kind = self._review_kind(tool_name, data)
        if review_kind in ("build", "diagnostic"):
            diagnostics = (
                data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
            )
            sections["diagnostics"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "error_count": int(data.get("error_count") or 0),
                    "warning_count": int(data.get("warning_count") or 0),
                    "diagnostics": diagnostics[:10],
                }
            )
            return
        if review_kind == "test":
            summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
            sections["tests"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "summary": summary,
                }
            )
            return
        if review_kind == "coverage":
            summary = (
                data.get("coverage_summary")
                if isinstance(data.get("coverage_summary"), dict)
                else {}
            )
            sections["coverage"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "summary": summary,
                }
            )
            return
        if review_kind == "quality":
            sections["quality"].append(
                {
                    "tool_name": tool_name,
                    "review_kind": review_kind,
                    "success": success,
                    "call_id": payload.get("call_id"),
                    "passed": bool(data.get("passed")),
                    "reasons": list(data.get("reasons") or []),
                }
            )

    def _review_finding_from_tool(
        self,
        tool_name: str,
        success: bool,
        payload: Dict[str, Any],
        data: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        review_kind = self._review_kind(tool_name, data)
        if review_kind == "build" and not success:
            detail = self._review_primary_detail(data, payload.get("error"))
            return {
                "id": "build-failed-%s" % str(payload.get("call_id") or tool_name),
                "priority": 1,
                "severity": "high",
                "title": "Build failed",
                "body": detail,
                "evidence": [
                    {
                        "type": "tool_failure",
                        "tool_name": tool_name,
                        "call_id": payload.get("call_id"),
                    }
                ],
            }
        if review_kind == "test":
            summary = data.get("test_summary") if isinstance(data.get("test_summary"), dict) else {}
            failures = int(summary.get("failed") or data.get("test_failures") or 0)
            if (not success) or failures > 0:
                return {
                    "id": "tests-failed-%s" % str(payload.get("call_id") or tool_name),
                    "priority": 1,
                    "severity": "high",
                    "title": "Tests failing",
                    "body": "最近一次测试 recipe 报告了 %s 个失败测试。" % failures,
                    "evidence": [
                        {
                            "type": "test_summary",
                            "tool_name": tool_name,
                            "recipe_action": "test",
                            "failed": failures,
                        }
                    ],
                }
        if review_kind == "diagnostic":
            error_count = int(data.get("error_count") or 0)
            warning_count = int(data.get("warning_count") or 0)
            if (not success) or error_count > 0 or warning_count > 0:
                return {
                    "id": "%s-issues-%s" % (tool_name, str(payload.get("call_id") or tool_name)),
                    "priority": 2,
                    "severity": "medium",
                    "title": "%s reported diagnostics" % tool_name,
                    "body": "%s 返回 error=%s, warning=%s。"
                    % (tool_name, error_count, warning_count),
                    "evidence": [
                        {
                            "type": "diagnostics",
                            "tool_name": tool_name,
                            "error_count": error_count,
                            "warning_count": warning_count,
                        }
                    ],
                }
        if review_kind == "coverage":
            summary = (
                data.get("coverage_summary")
                if isinstance(data.get("coverage_summary"), dict)
                else {}
            )
            line_coverage = summary.get("line_coverage")
            if line_coverage is not None and float(line_coverage) < 80.0:
                return {
                    "id": "coverage-low-%s" % str(payload.get("call_id") or tool_name),
                    "priority": 2,
                    "severity": "medium",
                    "title": "Coverage below expected floor",
                    "body": "最近一次覆盖率结果显示 line coverage 为 %.2f%%，低于 80%% 经验阈值。"
                    % float(line_coverage),
                    "evidence": [
                        {
                            "type": "coverage",
                            "tool_name": tool_name,
                            "line_coverage": float(line_coverage),
                        }
                    ],
                }
        if review_kind == "quality" and not bool(data.get("passed", success)):
            reasons = data.get("reasons") if isinstance(data.get("reasons"), list) else []
            body = (
                "；".join([str(item) for item in reasons if str(item or "").strip()])
                or "质量门未通过。"
            )
            return {
                "id": "quality-gate-failed-%s" % str(payload.get("call_id") or tool_name),
                "priority": 1,
                "severity": "high",
                "title": "Quality gate failed",
                "body": body,
                "evidence": [{"type": "quality_gate", "tool_name": tool_name, "reasons": reasons}],
            }
        return None

    def _review_kind(self, tool_name: str, data: Dict[str, Any]) -> str:
        del tool_name
        action = recipe_action_from_data(data)
        if action:
            if action in ("configure", "build"):
                return "build"
            if action == "test" or isinstance(data.get("test_summary"), dict):
                return "test"
            if action == "coverage" or isinstance(data.get("coverage_summary"), dict):
                return "coverage"
            if action in ("tidy", "analyze"):
                return "diagnostic"
            if isinstance(data.get("diagnostics"), list):
                return "diagnostic"
            return ""
        if is_quality_gate_data(data):
            return "quality"
        return ""

    def _review_primary_detail(self, data: Dict[str, Any], fallback: Any) -> str:
        diagnostics = data.get("diagnostics") if isinstance(data.get("diagnostics"), list) else []
        if diagnostics:
            first = diagnostics[0] if isinstance(diagnostics[0], dict) else {}
            return "%s:%s:%s %s" % (
                first.get("file") or "?",
                first.get("line") or 1,
                first.get("column") or 1,
                first.get("message") or (fallback or "编译失败。"),
            )
        return str(fallback or "编译失败。")
