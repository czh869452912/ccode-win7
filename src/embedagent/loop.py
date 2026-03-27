from __future__ import annotations

from typing import Callable, Optional, Tuple

from embedagent.llm import OpenAICompatibleClient
from embedagent.session import Action, Observation, Session
from embedagent.tools import ToolRuntime


DEFAULT_SYSTEM_PROMPT = (
    "你是 EmbedAgent 的最小可运行原型。"
    "请优先用中文回答，并在需要查看或修改工作区文件时主动调用工具。"
    "拿到工具 Observation 后，再基于结果给出简洁、明确的最终回复。"
)


class AgentLoop(object):
    def __init__(
        self,
        client: OpenAICompatibleClient,
        tools: ToolRuntime,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_turns: int = 8,
    ) -> None:
        self.client = client
        self.tools = tools
        self.system_prompt = system_prompt
        self.max_turns = max_turns

    def run(
        self,
        user_text: str,
        stream: bool = True,
        on_text_delta: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[Action], None]] = None,
        on_tool_finish: Optional[
            Callable[[Action, Observation], None]
        ] = None,
    ) -> Tuple[str, Session]:
        session = Session()
        session.add_system_message(self.system_prompt)
        session.add_user_message(user_text)
        final_text = ""
        for _ in range(self.max_turns):
            if stream:
                reply = self.client.stream(
                    session.api_messages(),
                    tools=self.tools.schemas(),
                    on_text_delta=on_text_delta,
                )
            else:
                reply = self.client.generate(
                    session.api_messages(),
                    tools=self.tools.schemas(),
                )
                if on_text_delta and reply.content:
                    on_text_delta(reply.content)
            session.add_assistant_reply(reply)
            final_text = reply.content
            if not reply.actions:
                return final_text, session
            for action in reply.actions:
                if on_tool_start:
                    on_tool_start(action)
                observation = self.tools.execute(action.name, action.arguments)
                session.add_observation(action, observation)
                if on_tool_finish:
                    on_tool_finish(action, observation)
        raise RuntimeError("超过最大迭代次数，主循环已停止。")
