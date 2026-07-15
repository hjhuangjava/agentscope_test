import type { AgentEvent } from "@agentscope-ai/agentscope/event";
import type { Msg } from "@agentscope-ai/agentscope/message";
import { streamBridgeChat } from "./bridgeClient";

export interface ChatRequest {
  question: string;
}

export type WorkflowControlEvent =
  | { type: "WORKFLOW_START"; question: string }
  | { type: "WORKFLOW_DONE" }
  | { type: "ERROR"; detail: string };

export type WorkflowMsgEvent = {
  type: "WORKFLOW_MSG";
  node: string;
  message: Msg;
};

export type StreamPayload = AgentEvent | WorkflowControlEvent | WorkflowMsgEvent;

const WORKFLOW_CONTROL_TYPES = new Set(["WORKFLOW_START", "WORKFLOW_DONE", "ERROR", "WORKFLOW_MSG"]);

export function isWorkflowControlPayload(
  payload: StreamPayload,
): payload is WorkflowControlEvent | WorkflowMsgEvent {
  return "type" in payload && WORKFLOW_CONTROL_TYPES.has(payload.type as string);
}

export function isWorkflowStart(payload: StreamPayload): payload is { type: "WORKFLOW_START"; question: string } {
  return "type" in payload && payload.type === "WORKFLOW_START";
}

export function isWorkflowDone(payload: StreamPayload): payload is { type: "WORKFLOW_DONE" } {
  return "type" in payload && payload.type === "WORKFLOW_DONE";
}

export function isWorkflowError(payload: StreamPayload): payload is { type: "ERROR"; detail: string } {
  return "type" in payload && payload.type === "ERROR";
}

export function isWorkflowMsgEvent(payload: StreamPayload): payload is WorkflowMsgEvent {
  return "type" in payload && payload.type === "WORKFLOW_MSG";
}

async function* readSseStream(response: Response): AsyncGenerator<StreamPayload> {
  if (!response.body) throw new Error("Empty response body");

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
      yield JSON.parse(line.slice(6)) as StreamPayload;
    }
  }
}

/** 最小 Agent 测试接口 */
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
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  yield* readSseStream(response);
}

/** 最小样例：直连 agent_stream_app.py，订阅 AgentEvent 流（POST /api/agent/stream） */
export async function* streamAgentEvents(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamPayload> {
  const response = await fetch("/api/agent/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  yield* readSseStream(response);
}

/** LangGraph × AgentScope bridge（langgraph_bridge_app :8000） */
export async function* streamBridgeChatEvents(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamPayload> {
  for await (const event of streamBridgeChat(request.question, signal)) {
    yield event;
  }
}

/** LangGraph workflow 接口（workflow_langgraph_app :8093，备用） */
export async function* streamWorkflowEvents(
  request: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<StreamPayload> {
  const response = await fetch("/api/workflow/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  yield* readSseStream(response);
}

export function isAgentEvent(payload: StreamPayload): payload is AgentEvent {
  return "type" in payload && !isWorkflowControlPayload(payload);
}
