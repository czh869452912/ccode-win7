from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Tuple

from embedagent_protocol import InteractionDescriptor, ShellDescriptor

_SUPPORTED_RENDERERS = frozenset(("interaction",))


class UnsupportedInteraction(ValueError):
    pass


class InteractionResponseError(ValueError):
    pass


@dataclass(frozen=True)
class InteractionChoice(object):
    key: str
    label: str
    value: str


@dataclass(frozen=True)
class InteractionPrompt(object):
    descriptor: InteractionDescriptor
    interaction_id: str
    kind: str
    prompt: str
    choices: Tuple[InteractionChoice, ...]
    default: str = ""
    answer_key: str = ""
    allow_custom: bool = False


def _interaction_kind(event_kind: str, payload: Mapping[str, Any]) -> str:
    if event_kind == "approval.requested":
        return "permission"
    if event_kind == "user-input.requested":
        return "user_input"
    return str(payload.get("kind") or "").strip()


def _descriptor(shell: ShellDescriptor, kind: str) -> InteractionDescriptor:
    if not isinstance(shell, ShellDescriptor):
        raise TypeError("shell must be a ShellDescriptor")
    matches = [item for item in shell.interactions if item.kind == kind]
    if len(matches) != 1:
        raise UnsupportedInteraction("unsupported_interaction:%s" % kind)
    if matches[0].renderer_key not in _SUPPORTED_RENDERERS:
        raise UnsupportedInteraction(
            "unsupported_interaction_renderer:%s" % matches[0].renderer_key
        )
    return matches[0]


def _permission_prompt(
    descriptor: InteractionDescriptor,
    interaction_id: str,
    payload: Mapping[str, Any],
) -> InteractionPrompt:
    prompt = str(payload.get("reason") or "Permission required").strip()
    choices = (
        InteractionChoice("1", "Allow once", "accept"),
        InteractionChoice("2", "Allow for session", "acceptForSession"),
        InteractionChoice("3", "Decline", "decline"),
        InteractionChoice("4", "Cancel turn", "cancel"),
    )
    return InteractionPrompt(
        descriptor=descriptor,
        interaction_id=interaction_id,
        kind="permission",
        prompt=prompt,
        choices=choices,
        default="decline",
    )


def _user_input_prompt(
    descriptor: InteractionDescriptor,
    interaction_id: str,
    payload: Mapping[str, Any],
) -> InteractionPrompt:
    questions = payload.get("questions")
    questions = questions if isinstance(questions, list) else []
    question = questions[0] if questions and isinstance(questions[0], dict) else {}
    prompt = str(question.get("question") or payload.get("question") or "Input required").strip()
    answer_key = str(question.get("id") or "answer").strip() or "answer"
    raw_options = question.get("options", payload.get("options", []))
    raw_options = raw_options if isinstance(raw_options, list) else []
    choices = []
    default = str(question.get("default") or payload.get("default") or "").strip()
    for position, item in enumerate(raw_options, start=1):
        if not isinstance(item, Mapping):
            continue
        key = str(item.get("index") or position)
        label = str(item.get("label") or item.get("text") or item.get("value") or "").strip()
        value = str(item.get("value") or label).strip()
        if not label or not value:
            continue
        choices.append(InteractionChoice(key, label, value))
        if bool(item.get("default")) and not default:
            default = value
    if bool(question.get("multi_select") or question.get("multiSelect")):
        raise UnsupportedInteraction("unsupported_interaction:multi_select")
    return InteractionPrompt(
        descriptor=descriptor,
        interaction_id=interaction_id,
        kind="user_input",
        prompt=prompt,
        choices=tuple(choices),
        default=default,
        answer_key=answer_key,
        allow_custom=True,
    )


def resolve_interaction(
    shell: ShellDescriptor,
    event_kind: str,
    payload: Mapping[str, Any],
) -> InteractionPrompt:
    if not isinstance(payload, Mapping):
        raise TypeError("interaction payload must be a mapping")
    kind = _interaction_kind(str(event_kind or ""), payload)
    descriptor = _descriptor(shell, kind)
    interaction_id = str(
        payload.get("interaction_id")
        or payload.get("request_id")
        or payload.get("permission_id")
        or ""
    ).strip()
    if not interaction_id:
        raise ValueError("interaction_id is required")
    if kind == "permission":
        return _permission_prompt(descriptor, interaction_id, payload)
    if kind == "user_input":
        return _user_input_prompt(descriptor, interaction_id, payload)
    raise UnsupportedInteraction("unsupported_interaction:%s" % kind)


def _selected_value(prompt: InteractionPrompt, raw: str) -> str:
    value = str(raw or "").strip()
    if not value:
        value = prompt.default
    normalized = value.lower()
    if prompt.kind == "permission":
        aliases = {
            "y": "accept",
            "yes": "accept",
            "n": "decline",
            "no": "decline",
        }
        value = aliases.get(normalized, value)
        normalized = value.lower()
    for choice in prompt.choices:
        if value == choice.key or normalized in (
            choice.label.lower(),
            choice.value.lower(),
        ):
            return choice.value
    if value and prompt.allow_custom:
        return value
    raise InteractionResponseError("invalid_interaction_response")


def build_interaction_response(
    prompt: InteractionPrompt,
    value: str,
) -> Dict[str, Any]:
    if not isinstance(prompt, InteractionPrompt):
        raise TypeError("prompt must be an InteractionPrompt")
    selected = _selected_value(prompt, value)
    if prompt.kind == "permission":
        return {"decision": selected}
    return {"answers": {prompt.answer_key or "answer": selected}}
