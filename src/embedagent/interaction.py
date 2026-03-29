from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class UserInputOption:
    index: int
    text: str
    mode: str = ""


@dataclass
class UserInputRequest:
    tool_name: str
    question: str
    options: List[UserInputOption]
    details: Dict[str, Any]


@dataclass
class UserInputResponse:
    answer: str
    selected_index: Optional[int] = None
    selected_mode: str = ""
    selected_option_text: str = ""


def ask_user_schema() -> Dict[str, object]:
    properties = {
        "question": {
            "type": "string",
            "description": "要向用户提出的明确问题。应聚焦当前阻塞点。示例：是否现在切到 code 模式开始实现？",
        },
    }
    required = ["question", "option_1", "option_2"]
    for index in range(1, 5):
        properties["option_%s" % index] = {
            "type": "string",
            "description": "第 %s 个建议选项文本。应是完整可执行的回答。示例：是，切到 code 模式并开始实现。" % index,
        }
        properties["option_%s_mode" % index] = {
            "type": "string",
            "description": "第 %s 个选项对应的模式名，留空表示不切模式。示例：code" % index,
        }
    return {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "向用户提一个阻塞当前任务的问题。用于在继续前确认方向、范围或模式选择。提供 2 到 4 个建议选项，用户也可自由输入。",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


def build_user_input_request(arguments: Dict[str, Any]) -> UserInputRequest:
    question = str(arguments.get("question") or "").strip()
    options = []  # type: List[UserInputOption]
    for index in range(1, 5):
        text = str(arguments.get("option_%s" % index) or "").strip()
        if not text:
            continue
        mode = str(arguments.get("option_%s_mode" % index) or "").strip()
        options.append(UserInputOption(index=index, text=text, mode=mode))
    return UserInputRequest(
        tool_name="ask_user",
        question=question,
        options=options,
        details={
            "question": question,
            "options": [
                {"index": item.index, "text": item.text, "mode": item.mode}
                for item in options
            ],
        },
    )
