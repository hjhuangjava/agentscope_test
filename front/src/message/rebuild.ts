import {
  AssistantMsg,
  appendEvent,
  getContentBlocks,
  getTextContent,
  type Msg,
} from "@agentscope-ai/agentscope/message";
import { EventType, type AgentEvent } from "@agentscope-ai/agentscope/event";

/** 按官方文档，从事件流增量重建 assistant Msg。 */
export function rebuildMessageFromEvents(events: AsyncIterable<AgentEvent>): {
  consume: () => Promise<Msg | null>;
} {
  let msg: Msg | null = null;

  async function consume(): Promise<Msg | null> {
    for await (const event of events) {
      if (event.type === EventType.REPLY_START) {
        msg = AssistantMsg({
          name: event.name,
          content: [],
          id: event.reply_id,
        });
        continue;
      }
      if (msg) {
        appendEvent(msg, event);
      }
    }
    return msg;
  }

  return { consume };
}

/** 单条事件增量更新 Msg（用于流式 UI 渲染）。 */
export function applyEvent(msg: Msg | null, event: AgentEvent): Msg | null {
  if (event.type === EventType.REPLY_START) {
    return AssistantMsg({
      name: event.name,
      content: [],
      id: event.reply_id,
    });
  }
  if (!msg) return null;
  return appendEvent(msg, event);
}

export function getThinkingContent(msg: Msg): string {
  return getContentBlocks(msg, "thinking")
    .map((block) => block.thinking)
    .join("\n")
    .trim();
}

export function formatToolOutput(output: string | Array<{ type: string; text?: string }>): string {
  if (typeof output === "string") return output;
  return output
    .map((block) => (block.type === "text" ? block.text ?? "" : JSON.stringify(block, null, 2)))
    .join("\n");
}

export { getTextContent };
