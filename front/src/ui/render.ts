import type { Msg } from "@agentscope-ai/agentscope/message";
import { getTextContent, getThinkingContent, formatToolOutput } from "../message/rebuild";

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

export function renderUserBubble(question: string): HTMLElement {
  const wrapper = document.createElement("div");
  wrapper.className = "message user";
  wrapper.innerHTML = `
    <div class="meta">user</div>
    <div class="bubble">${escapeHtml(question)}</div>
  `;
  return wrapper;
}

export function renderWorkflowBubble(node: string, msg: Msg): HTMLElement {
  const wrapper = document.createElement("article");
  wrapper.className = `message workflow ${msg.role}`;
  const content = getTextContent(msg) ?? "";
  wrapper.innerHTML = `
    <div class="meta">workflow · ${escapeHtml(node)} · ${escapeHtml(msg.role)}</div>
    <div class="bubble">${escapeHtml(content)}</div>
  `;
  return wrapper;
}

export function renderAssistantBubble(msg: Msg): HTMLElement {
  const wrapper = document.createElement("article");
  wrapper.className = "message assistant";
  wrapper.dataset.replyId = msg.id;

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${msg.name} · ${msg.finished_at ? "已完成" : "生成中..."}`;
  wrapper.appendChild(meta);

  const bubble = document.createElement("div");
  bubble.className = "bubble";

  const thinking = getThinkingContent(msg);
  if (thinking) {
    const details = document.createElement("details");
    details.className = "thinking";
    details.open = !msg.finished_at;
    details.innerHTML = `<summary>思考过程</summary>`;
    const thinkingBody = document.createElement("div");
    thinkingBody.className = "block block-thinking";
    thinkingBody.textContent = thinking;
    details.appendChild(thinkingBody);
    bubble.appendChild(details);
  }

  for (const block of msg.content) {
    if (block.type === "text" && block.text) {
      const textEl = document.createElement("div");
      textEl.className = "block block-text";
      textEl.textContent = block.text;
      bubble.appendChild(textEl);
    }

    if (block.type === "tool_call") {
      const toolEl = document.createElement("div");
      toolEl.className = "block block-tool-call";
      toolEl.innerHTML = `
        <div class="block-title">工具调用 · ${escapeHtml(block.name)}</div>
        <div class="block-body">${escapeHtml(block.input || "")}</div>
      `;
      bubble.appendChild(toolEl);
    }

    if (block.type === "tool_result") {
      const resultEl = document.createElement("div");
      resultEl.className = "block block-tool-result";
      resultEl.innerHTML = `
        <div class="block-title">工具结果 · ${escapeHtml(block.name)} · ${escapeHtml(block.state)}</div>
        <div class="block-body">${escapeHtml(formatToolOutput(block.output))}</div>
      `;
      bubble.appendChild(resultEl);
    }
  }

  if (!bubble.children.length) {
    const placeholder = document.createElement("div");
    placeholder.className = "block block-text";
    placeholder.textContent = "等待 Agent 回复...";
    bubble.appendChild(placeholder);
  }

  wrapper.appendChild(bubble);

  const answer = getTextContent(msg);
  if (msg.usage || answer) {
    const footer = document.createElement("div");
    footer.className = "usage";
    const parts: string[] = [];
    if (answer) parts.push(`answer chars: ${answer.length}`);
    if (msg.usage) {
      parts.push(`tokens in=${msg.usage.input_tokens}, out=${msg.usage.output_tokens}`);
    }
    footer.textContent = parts.join(" · ");
    wrapper.appendChild(footer);
  }

  return wrapper;
}

export function replaceNode(oldNode: HTMLElement, newNode: HTMLElement): HTMLElement {
  oldNode.replaceWith(newNode);
  return newNode;
}
