"""
通过本地 vLLM (OpenAI 兼容接口) 跑通 AgentScope 2.x 对话示例。

依赖环境：conda activate agentscope
运行：python run_local_model.py
"""

import asyncio

from agentscope.credential import OpenAICredential
from agentscope.model import OpenAIChatModel
from agentscope.message import Msg


VL_MODEL_URL = "http://192.168.39.100:11806/v1"
VL_MODEL_NAME = "qwen3.6:35b"
VL_MODEL_TOKEN = "empty"  # 本地无鉴权，但 SDK 要求非空，用占位字符串


async def main() -> None:
    credential = OpenAICredential(
        api_key=VL_MODEL_TOKEN,
        base_url=VL_MODEL_URL,
    )

    model = OpenAIChatModel(
        credential=credential,
        model=VL_MODEL_NAME,
        stream=False,
        client_kwargs={"timeout": 120},
    )

    user_msg = Msg(
        role="user",
        name="user",
        content=[{"type": "text", "text": "用一句话介绍你自己，并说出 1+1 等于几。"}],
    )

    print(f"[user] {user_msg.content[0].text}\n")

    response = await model([user_msg])

    # 模型可能返回 ThinkingBlock / TextBlock，分别打印
    for block in response.content:
        btype = getattr(block, "type", None)
        if btype == "thinking":
            print(f"[thinking] {getattr(block, 'thinking', '')}\n")
        elif btype == "text":
            print(f"[assistant] {getattr(block, 'text', '')}")
        else:
            print(f"[{btype}] {block}")


if __name__ == "__main__":
    asyncio.run(main())
