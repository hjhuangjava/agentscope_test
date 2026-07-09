import type { AgentEvent } from "@agentscope-ai/agentscope/event";

export interface ChatRequest {
  question: string;
  user_id?: string;
  session_id?: string;
}

export type WorkflowControlEvent =
  | { type: "WORKFLOW_START"; question: string }
  | { type: "WORKFLOW_DONE" }
  | { type: "ERROR"; detail: string };

export type StreamPayload = AgentEvent | WorkflowControlEvent;

function isWorkflowControlEvent(payload: StreamPayload): payload is WorkflowControlEvent {
  return (
    payload.type === "WORKFLOW_START" ||
    payload.type === "WORKFLOW_DONE" ||
    payload.type === "ERROR"
  );
}

/** 读取 POST SSE 流，逐条解析 AgentScope 事件。 */
export async function* streamChatEvents(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamPayload> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });

  if (!response.ok || !response.body) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk.split("\n").find((item) => item.startsWith("data: "));
      if (!line) continue;

      const payload = JSON.parse(line.slice(6)) as StreamPayload;
      yield payload;
    }
  }
}

export function isAgentEvent(payload: StreamPayload): payload is AgentEvent {
  return !isWorkflowControlEvent(payload);
}
