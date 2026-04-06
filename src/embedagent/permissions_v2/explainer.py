from __future__ import annotations


def build_permission_explanation(
    tool_name,
    args_summary,
    risk_category,
    trigger_reason,
    rule_source,
    scope_text,
    memory_scope,
):
    return "\n".join(
        [
            "[请求] %s(%s)" % (tool_name, args_summary),
            "[风险] %s" % risk_category,
            "[原因] %s" % trigger_reason,
            "[规则] %s" % rule_source,
            "[范围] %s" % scope_text,
            "[记忆] %s" % memory_scope,
        ]
    )
