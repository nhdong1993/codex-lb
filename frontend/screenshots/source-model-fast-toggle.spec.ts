import path from "node:path";
import { expect, test } from "@playwright/test";
import { authSession, settings, upstreamProxyAdmin } from "./fixtures";

const TIMESTAMP = "2026-10-17T00:00:00Z";
const REASONING = { default_reasoning_level: "medium", supported_reasoning_levels: ["low", "medium", "high"], supports_reasoning: true };
const FAST = { service_tiers: [{ id: "priority", name: "Fast", description: "Priority processing" }], additional_speed_tiers: ["fast"] };

function sourceModel(id: number, model: string, upstreamModel: string, extra: Record<string, unknown> = {}) {
  return {
    id, sourceId: "src_relay", model, displayName: model, contextWindow: 272000, maxOutputTokens: null,
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
    sourceModel(1, "ch-relay/gpt-6-astra", "gpt-6-astra", { block_subagents: true, ...FAST }),
    sourceModel(2, "ch-relay/gpt-6.1-sol", "gpt-6.1-sol"),
    sourceModel(3, "http/gpt-6-astra", "gpt-6-astra", { block_subagents: true }),
    sourceModel(4, "http/gpt-6-sol", "gpt-6-sol"),
  ],
};

test("model source editor Fast switch", async ({ page }) => {
  const phase = process.env.SOURCE_FAST_SCREENSHOT_PHASE ?? "after";
  const mobile = process.env.SOURCE_FAST_SCREENSHOT_MOBILE === "1";
  if (mobile) await page.setViewportSize({ width: 390, height: 844 });
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
  await page.goto(`${process.env.SOURCE_FAST_SCREENSHOT_URL ?? "http://127.0.0.1:4191"}/settings`);
  await page.getByRole("button", { name: "Show advanced settings" }).click();
  await page.getByRole("button", { name: "Edit ch-relay (VPS) model source" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  if (phase !== "before") {
    await expect(dialog.getByRole("switch", { name: "Offer Fast mode on ch-relay/gpt-6-astra" })).toBeChecked();
    await dialog.getByRole("switch", { name: "Offer Fast mode on http/gpt-6-astra" }).click();
  }
  await dialog.evaluate((element) => {
    element.style.maxHeight = "none";
    element.style.overflow = "visible";
  });
  await dialog.screenshot({
    path: path.resolve(`../openspec/changes/toggle-source-model-fast-mode/evidence/edit-dialog-${phase}${mobile ? "-mobile" : ""}.png`),
  });
});
