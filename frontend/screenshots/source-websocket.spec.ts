import path from "node:path";
import { expect, test } from "@playwright/test";
import { authSession, settings, upstreamProxyAdmin } from "./fixtures";

test("model source native websocket capability", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("i18nextLng", "en"));
  await page.route("**/api/**", async (route) => {
    const p = new URL(route.request().url()).pathname;
    const data = p === "/api/dashboard-auth/session" ? authSession
      : p === "/api/settings" ? settings
      : p === "/api/settings/upstream-proxy" ? upstreamProxyAdmin
      : p.startsWith("/api/model-sources") ? { sources: [] }
      : p === "/api/models" ? { models: [] }
      : p.startsWith("/api/firewall") ? { entries: [] }
      : {};
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(data) });
  });
  await page.goto(`${process.env.SOURCE_WS_SCREENSHOT_URL ?? "http://127.0.0.1:4189"}/settings`);
  await page.getByRole("button", { name: "Show advanced settings" }).click();
  await page.getByRole("button", { name: "Add source", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  if (process.env.SOURCE_WS_SCREENSHOT_PHASE !== "before") {
    const websocket = dialog.getByRole("checkbox", { name: "Responses WebSocket", exact: true });
    await websocket.click();
    await expect(dialog.getByRole("checkbox", { name: "Responses", exact: true })).toBeChecked();
    await expect(dialog.getByRole("checkbox", { name: "Streaming", exact: true })).toBeChecked();
  }
  await dialog.screenshot({ path: path.resolve(`../openspec/changes/add-model-source-websocket/evidence/form-${process.env.SOURCE_WS_SCREENSHOT_PHASE ?? "after"}.png`) });
});
