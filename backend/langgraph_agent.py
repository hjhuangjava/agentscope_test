"""
LangGraphAgent：推理委托给 LangGraph，事件流仍走 AgentScope 协议。

对接方式（AgentScope 2.0.3）：
- ChatService 通过 create_app(custom_agent_cls=...) 组装本类
- 覆写 _reply_impl（保留 _reply 的中间件钩子）
- yield 标准 AgentEvent，ChatService / SSE 客户端用 append_event 重建 Msg
"""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional
from uuid import uuid4

from agentscope.agent import Agent
from agentscope._utils._common import _generate_id
from agentscope.event import (
    AgentEvent,
    ExternalExecutionResultEvent,
    HintBlockEvent,
    ReplyEndEvent,
    ReplyStartEvent,
    TextBlockDeltaEvent,
    TextBlockEndEvent,
    TextBlockStartEvent,
    UserConfirmResultEvent,
)
from agentscope.message import (
    AssistantMsg,
    Msg,
    TextBlock,
)
from langgraph.graph.state import CompiledStateGraph

from langgraph_workflow import create_langgraph_workflow


class LangGraphAgent(Agent):
    """Agent 子类：编排走 LangGraph，基础设施复用 AgentScope。"""

    def __init__(self, *args: Any, graph: CompiledStateGraph | None = None, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self._graph = graph or create_langgraph_workflow()

    async def _reply_impl(
        self,
        inputs: Msg
        | list[Msg]
        | UserConfirmResultEvent
        | ExternalExecutionResultEvent
        | None = None,
    ) -> AsyncGenerator[AgentEvent | Msg, None]:
        # HITL 续跑仍走默认实现
        if isinstance(inputs, (UserConfirmResultEvent, ExternalExecutionResultEvent)):
            async for item in super()._reply_impl(inputs=inputs):
                yield item
            return

        await self._handle_incoming_messages(inputs)
        self.state.reply_id = _generate_id()
        self.state.cur_iter = 0

        yield ReplyStartEvent(
            session_id=self.state.session_id,
            reply_id=self.state.reply_id,
            name=self.name,
        )

        query = self._extract_latest_user_text(inputs)
        accumulated: dict[str, Any] = {
            "user_input": query,
            "node_logs": [],
        }

        # LangGraph 按节点更新；每个节点完成后发 HintBlock，前端可订阅
        async for update in self._graph.astream(
            accumulated,
            stream_mode="updates",
            config={
                "configurable": {
                    "thread_id": self.state.session_id or "default",
                    "agentscope_model": self.model,
                    "system_prompt": self._system_prompt,
                }
            },
        ):
            for node_name, patch in update.items():
                accumulated.update(patch)
                logs = patch.get("node_logs") or []
                detail = logs[-1] if logs else f"{node_name} done"
                yield HintBlockEvent(
                    reply_id=self.state.reply_id,
                    block_id=f"hint-{node_name}-{uuid4().hex[:8]}",
                    hint=f"[workflow · {node_name}] {detail}",
                    source=json.dumps(
                        {
                            "kind": "workflow_node",
                            "node": node_name,
                            "detail": detail,
                            "keys": list(patch.keys()),
                        },
                        ensure_ascii=False,
                    ),
                )

        answer = (accumulated.get("final_answer") or "").strip() or "（未生成回答）"
        block_id = f"text-{uuid4().hex[:8]}"

        yield TextBlockStartEvent(reply_id=self.state.reply_id, block_id=block_id)
        # 简单按段推送，模拟流式；前端 appendEvent 即可重建
        for chunk in _chunk_text(answer, size=24):
            yield TextBlockDeltaEvent(
                reply_id=self.state.reply_id,
                block_id=block_id,
                delta=chunk,
            )
        yield TextBlockEndEvent(reply_id=self.state.reply_id, block_id=block_id)

        yield ReplyEndEvent(
            session_id=self.state.session_id,
            reply_id=self.state.reply_id,
        )

        assistant_msg = AssistantMsg(
            id=self.state.reply_id,
            name=self.name,
            content=[TextBlock(id=block_id, text=answer)],
        )
        self.state.context.append(assistant_msg)
        yield assistant_msg

    @staticmethod
    def _extract_latest_user_text(
        inputs: Msg | list[Msg] | None,
    ) -> str:
        if inputs is None:
            return ""
        msgs = [inputs] if isinstance(inputs, Msg) else list(inputs)
        for msg in reversed(msgs):
            if msg.role == "user":
                return (msg.get_text_content() or "").strip()
        if msgs:
            return (msgs[-1].get_text_content() or "").strip()
        return ""


def make_langgraph_agent_cls(
    graph: Optional[CompiledStateGraph] = None,
) -> type[LangGraphAgent]:
    """工厂：供 create_app(custom_agent_cls=...) 注入，图可共享单例。"""
    shared_graph = graph or create_langgraph_workflow()

    class BoundLangGraphAgent(LangGraphAgent):
        def __init__(self, *args: Any, **kwargs: Any):
            super().__init__(*args, graph=shared_graph, **kwargs)

    BoundLangGraphAgent.__name__ = "BoundLangGraphAgent"
    return BoundLangGraphAgent


def _chunk_text(text: str, size: int = 24) -> list[str]:
    if not text:
        return [""]
    return [text[i : i + size] for i in range(0, len(text), size)]
