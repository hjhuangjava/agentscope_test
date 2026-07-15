/**
 * AgentScope create_app（langgraph_bridge_app :8000）客户端。
 *
 * 流程：bootstrap credential/agent/session → GET SSE 订阅 → POST /chat/ 触发
 */
import type { AgentEvent } from "@agentscope-ai/agentscope/event";
import { EventType } from "@agentscope-ai/agentscope/event";

const USER_ID = import.meta.env.VITE_BRIDGE_USER_ID ?? "demo-user";
const MODEL_URL = import.meta.env.VITE_BRIDGE_MODEL_URL ?? "http://192.168.39.100:11806/v1";
const MODEL_NAME = import.meta.env.VITE_BRIDGE_MODEL_NAME ?? "qwen3.6:35b";
const MODEL_TOKEN = import.meta.env.VITE_BRIDGE_MODEL_TOKEN ?? "empty";
const STORAGE_KEY = "agentscope-bridge-ids";

interface BridgeContext {
  userId: string;
  agentId: string;
  sessionId: string;
}

interface StoredIds {
  agentId: string;
  sessionId: string;
}

function bridgeHeaders(json = false): HeadersInit {
  const headers: Record<string, string> = { "X-User-ID": USER_ID };
  if (json) headers["Content-Type"] = "application/json";
  return headers;
}

async function readJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text || response.statusText}`);
  }
  return (await response.json()) as T;
}

async function* readAgentEventSse(
  response: Response,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  if (!response.body) throw new Error("Empty SSE response body");

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (!signal?.aborted) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const line = chunk.split("\n").find((item) => item.startsWith("data: "));
      if (!line) continue;
      yield JSON.parse(line.slice(6)) as AgentEvent;
    }
  }
}

let bootstrapPromise: Promise<BridgeContext> | null = null;

async function bootstrap(): Promise<BridgeContext> {
  const cached = localStorage.getItem(STORAGE_KEY);
  if (cached) {
    const ids = JSON.parse(cached) as StoredIds;
    return { userId: USER_ID, agentId: ids.agentId, sessionId: ids.sessionId };
  }

  const credential = await readJson<{ credential_id: string }>(
    await fetch("/credential/", {
      method: "POST",
      headers: bridgeHeaders(true),
      body: JSON.stringify({
        data: {
          type: "openai_credential",
          api_key: MODEL_TOKEN,
          base_url: MODEL_URL,
        },
      }),
    }),
  );

  const agent = await readJson<{ agent_id: string }>(
    await fetch("/agent/", {
      method: "POST",
      headers: bridgeHeaders(true),
      body: JSON.stringify({
        name: "langgraph-bridge",
        system_prompt: "You are a helpful assistant. Answer clearly in Chinese.",
      }),
    }),
  );

  const session = await readJson<{ session_id: string }>(
    await fetch("/sessions/", {
      method: "POST",
      headers: bridgeHeaders(true),
      body: JSON.stringify({
        agent_id: agent.agent_id,
        chat_model_config: {
          type: "openai_credential",
          credential_id: credential.credential_id,
          model: MODEL_NAME,
          parameters: { stream: false },
        },
      }),
    }),
  );

  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ agentId: agent.agent_id, sessionId: session.session_id }),
  );

  return {
    userId: USER_ID,
    agentId: agent.agent_id,
    sessionId: session.session_id,
  };
}

export async function getBridgeContext(): Promise<BridgeContext> {
  if (!bootstrapPromise) bootstrapPromise = bootstrap();
  return bootstrapPromise;
}

/** 订阅 session SSE，并在 POST /chat/ 后读取直到 REPLY_END。 */
export async function* streamBridgeChat(
  question: string,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  const ctx = await getBridgeContext();
  const streamUrl =
    `/sessions/${encodeURIComponent(ctx.sessionId)}/stream` +
    `?agent_id=${encodeURIComponent(ctx.agentId)}`;

  const sseResponse = await fetch(streamUrl, {
    headers: bridgeHeaders(),
    signal,
  });
  if (!sseResponse.ok) {
    throw new Error(`SSE subscribe failed: HTTP ${sseResponse.status}`);
  }

  const events = readAgentEventSse(sseResponse, signal);
  const nextEvent = events.next();

  await readJson(
    await fetch("/chat/", {
      method: "POST",
      headers: bridgeHeaders(true),
      body: JSON.stringify({
        agent_id: ctx.agentId,
        session_id: ctx.sessionId,
        input: {
          name: "user",
          role: "user",
          content: [{ type: "text", text: question }],
        },
      }),
      signal,
    }),
  );

  let result = await nextEvent;
  while (!result.done) {
    yield result.value;
    if (result.value.type === EventType.REPLY_END) break;
    result = await events.next();
  }
}

export function resetBridgeBootstrap(): void {
  localStorage.removeItem(STORAGE_KEY);
  bootstrapPromise = null;
}
