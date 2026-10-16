import path from "node:path";
import { expect, test } from "@playwright/test";
import { authSession, settings, upstreamProxyAdmin } from "./fixtures";

const TIMESTAMP = "2026-10-16T00:00:00Z";
const REASONING = { default_reasoning_level: "medium", supported_reasoning_levels: ["low", "medium", "high"], supports_reasoning: true };

function sourceModel(id: number, model: string, upstreamModel: string, extra: Record<string, unknown> = {}) {
  return {
    id, sourceId: "src_relay", model, displayName: model, contextWindow: null, maxOutputTokens: null,
    supportsStreaming: true, supportsTools: true, supportsVision: false, inputPer1M: null, cachedInputPer1M: null,
    outputPer1M: null, audioPerMinute: null, isEnabled: true, createdAt: TIMESTAMP, updatedAt: TIMESTAMP,
    rawMetadataJson: JSON.stringify({ ...REASONING, upstream_model: upstreamModel, ...extra }),
  };
}

const relaySource = {
  id: "src_relay", name: "ch-relay (VPS)", kind: "openai_compatible", baseUrl: "http://172.31.245.1:11500/v1",
  isEnabled: true, healthStatus: "unknown", supportsChatCompletions: true, supportsResponses: true,
  supportsResponsesWebsocket: false, supportsAudioTranscriptions: false, supportsEmbeddings: false,
  timeoutSeconds: null, maxConcurrency: null, createdAt: TIMESTAMP, updatedAt: TIMESTAMP,
  models: [
    sourceModel(1, "ch-relay/gpt-6-astra", "gpt-6-astra"),
    sourceModel(2, "ch-relay/gpt-6.1-sol", "gpt-6.1-sol"),
    sourceModel(3, "http/gpt-6-astra", "gpt-6-astra"),
    sourceModel(4, "http/gpt-6-sol", "gpt-6-sol"),
    sourceModel(5, "http/gpt-6.1-sol", "gpt-6.1-sol"),
  ],
};

test("model source editor rows and tool forwarding", async ({ page }) => {
  const phase = process.env.SOURCE_EDITOR_SCREENSHOT_PHASE ?? "after";
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "en"));
  await page.route("**/api/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    const data = p === "/api/dashboard-auth/session" ? authSession
      : p === "/api/settings" ? settings
      : p === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
      : p.startsWith("/api/model-sources") ? { sources: [relaySource] }
      : p === "/api/models" ? { models: [] }
      : p.startsWith("/api/firewall") ? { entries: [] }
      : {};
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });
  await page.goto(`${process.env.SOURCE_EDITOR_SCREENSHOT_URL ?? "http://127.0.0.1:4191"}/settings`);
  await page.getByRole("button", { name: "Show advanced settings" }).click();
  await page.getByRole("button", { name: "Edit ch-relay (VPS) model source" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  if (phase !== "before") {
    await dialog.getByRole("checkbox", { name: "MCP & sub-agents" }).click();
    await dialog.getByRole("switch", { name: "Enable ch-relay/gpt-6.1-sol" }).click();
    await dialog.getByRole("switch", { name: "Allow sub-agents on http/gpt-6-astra" }).click();
  }
  await dialog.evaluate((element) => {
    element.style.maxHeight = "none";
    element.style.overflow = "visible";
  });
  await dialog.screenshot({
    path: path.resolve(`../openspec/changes/redesign-source-model-editor/evidence/edit-dialog-${phase}.png`),
  });
});
