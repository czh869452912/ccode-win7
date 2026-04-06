from __future__ import annotations


def apply_aggregate_budget(results, char_budget):
    total = 0
    reduced = []
    for item in list(results or []):
        preview = str(item.get("preview") or "")
        total += len(preview)
        if total > int(char_budget or 0):
            reduced.append(
                {
                    "tool_name": item.get("tool_name"),
                    "preview": "",
                    "result_ref": item.get("result_ref"),
                    "omitted": True,
                }
            )
            continue
        reduced.append(dict(item))
    return reduced
