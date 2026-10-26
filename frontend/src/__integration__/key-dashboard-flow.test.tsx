import { HttpResponse, http } from "msw";
import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "@/App";
import { KEY_DASHBOARD_API_KEY_STORAGE_KEY } from "@/features/key-dashboard/storage";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

const TEST_KEY = "sk-clb-key-dashboard-secret";

async function confirmKeepLoginExport(user: ReturnType<typeof userEvent.setup>) {
  const dialog = await screen.findByRole("alertdialog", { name: "Xác nhận gửi access token lên server" });
  await user.click(within(dialog).getByRole("button", { name: "Tôi hiểu, tiếp tục" }));
}

const safeLog = {
  requestedAt: "2026-09-03T12:00:00Z",
  requestId: "req-key-dashboard-1",
  requestKind: "normal",
  model: "gpt-5.1",
  transport: "http",
  upstreamTransport: "websocket",
  serviceTier: null,
  requestedServiceTier: null,
  actualServiceTier: null,
  reasoningEffort: "medium",
  status: "ok",
  errorCode: null,
  tokens: 125,
  inputTokens: 100,
  outputTokens: 25,
  outputTokensRaw: 25,
  reasoningTokens: 5,
  cachedInputTokens: 20,
  costUsd: 0.0123,
  costBreakdown: {
    inputUsd: 0.004,
    cachedInputUsd: 0.001,
    outputUsd: 0.0073,
    totalUsd: 0.0123,
  },
  latencyMs: 500,
  latencyFirstTokenMs: 100,
  latencyQueueMs: 20,
};

const safeProfile = {
  name: "Production client",
  keyPrefix: "sk-clb-key-dash…",
  isActive: true,
  createdAt: "2026-08-01T08:00:00Z",
  expiresAt: "2027-08-01T08:00:00Z",
  lastUsedAt: "2026-09-03T11:59:00Z",
  allowedModels: ["gpt-5.1", "gpt-5.2"],
  enforcedModel: null,
  allowedReasoningEfforts: ["low", "medium"],
  enforcedReasoningEffort: null,
  enforcedServiceTier: "priority",
  trafficClass: "foreground",
  transportPolicyOverride: "always_websocket",
};

const usagePayload = {
  request_count: 9,
  total_tokens: 12_500,
  cached_input_tokens: 2_500,
  total_cost_usd: 0.42,
  limits: [{
    limit_type: "total_tokens",
    limit_window: "weekly",
    max_value: 50_000,
    current_value: 12_500,
    remaining_value: 37_500,
    model_filter: "gpt-5.1",
    reset_at: "2026-09-10T08:00:00Z",
    source: "api_key_limit",
  }],
  upstream_limits: [],
  account_pool_usage: null,
};

describe("API key dashboard integration", () => {
  beforeEach(() => {
    window.history.pushState({}, "", "/key-dashboard");
    window.localStorage.removeItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY);
    useDateDisplayFormatStore.setState({ dateDisplayFormat: "iso8601" });
    server.use(http.get("/api/key-dashboard/group", () => HttpResponse.json({
      groupName: null, from: "2026-08-11T12:00:00Z", until: "2026-09-10T12:00:00Z", members: [],
    })));
  });

  afterEach(() => {
    useDateDisplayFormatStore.setState({ dateDisplayFormat: "default" });
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("bypasses administrator auth and loads only key-scoped safe data", async () => {
    const seenPaths: string[] = [];
    const credentials: RequestCredentials[] = [];
    const logOffsets: string[] = [];
    let usageCalls = 0;
    server.use(
      http.get("/api/dashboard-auth/session", () => {
        seenPaths.push("/api/dashboard-auth/session");
        return HttpResponse.json({ error: { code: "unexpected", message: "Unexpected admin auth" } }, { status: 500 });
      }),
      http.get("/v1/usage", ({ request }) => {
        seenPaths.push("/v1/usage");
        credentials.push(request.credentials);
        usageCalls += 1;
        expect(request.headers.get("Authorization")).toBe(`Bearer ${TEST_KEY}`);
        return HttpResponse.json(usagePayload);
      }),
      http.get("/api/key-dashboard/profile", ({ request }) => {
        seenPaths.push("/api/key-dashboard/profile");
        credentials.push(request.credentials);
        expect(request.headers.get("Authorization")).toBe(`Bearer ${TEST_KEY}`);
        return HttpResponse.json(safeProfile);
      }),
      http.get("/api/key-dashboard/request-logs", ({ request }) => {
        seenPaths.push("/api/key-dashboard/request-logs");
        credentials.push(request.credentials);
        expect(request.headers.get("Authorization")).toBe(`Bearer ${TEST_KEY}`);
        const offset = new URL(request.url).searchParams.get("offset") ?? "0";
        logOffsets.push(offset);
        return HttpResponse.json({
          requests: [{ ...safeLog, requestId: offset === "0" ? safeLog.requestId : "req-key-dashboard-page-2" }],
          total: 26,
          hasMore: offset === "0",
        });
      }),
    );
    const user = userEvent.setup();

    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "View your API key usage" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("API key"), TEST_KEY);
    await user.click(screen.getByRole("button", { name: "Open dashboard" }));

    expect(await screen.findByRole("heading", { name: "API key dashboard" })).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "View Details" }));
    expect(await screen.findByText("req-key-dashboard-1")).toBeInTheDocument();
    expect(screen.queryByText("User agent")).not.toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.getByText("12.5K")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Production client" })).toBeInTheDocument();
    expect(screen.getByText("sk-clb-key-dash…")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("08:00:00  01/08/2026", { exact: true, normalizer: (value) => value })).toBeInTheDocument();
    expect(screen.getByText("gpt-5.1, gpt-5.2")).toBeInTheDocument();
    expect(screen.queryByText("Effective policies")).not.toBeInTheDocument();
    expect(screen.queryByText("Traffic class")).not.toBeInTheDocument();
    expect(screen.queryByText("Transport policy")).not.toBeInTheDocument();
    expect(screen.getByText("Usage limits")).toBeInTheDocument();
    expect(screen.getByText("37.5K remaining")).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Account" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "API Key" })).not.toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Time" })).toHaveStyle({ width: "136px" });
    expect(seenPaths).toEqual(expect.arrayContaining([
      "/api/key-dashboard/profile",
      "/v1/usage",
      "/api/key-dashboard/request-logs",
    ]));
    expect(seenPaths).not.toContain("/api/dashboard-auth/session");
    expect(credentials).toHaveLength(3);
    expect(credentials.every((credential) => credential === "omit")).toBe(true);
    expect(window.location.pathname).toBe("/key-dashboard");
    expect(window.location.search).toBe("");
    expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();

    await user.click(screen.getByRole("button", { name: "Refresh" }));
    await waitFor(() => expect(usageCalls).toBe(2));
    await user.click(screen.getByRole("button", { name: "Next page" }));
    await waitFor(() => expect(logOffsets).toEqual(["0", "0", "25"]));
    expect(credentials).toHaveLength(9);
    expect(credentials.every((credential) => credential === "omit")).toBe(true);
    expect(window.location.search).toBe("");

    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(await screen.findByRole("heading", { name: "View your API key usage" })).toBeInTheDocument();
    expect(screen.getByLabelText("API key")).toHaveValue("");
    expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();
  });

  function mockDashboard() {
    server.use(
      http.get("/api/key-dashboard/profile", () => HttpResponse.json(safeProfile)),
      http.get("/v1/usage", () => HttpResponse.json(usagePayload)),
      http.get("/api/key-dashboard/request-logs", () => HttpResponse.json({ requests: [], total: 0, hasMore: false })),
    );
  }

  async function connect(user: ReturnType<typeof userEvent.setup>, key = TEST_KEY) {
    await user.type(await screen.findByLabelText("API key"), key);
    await user.click(screen.getByRole("button", { name: "Open dashboard" }));
    await screen.findByRole("tab", { name: "Install" });
  }

  const groupPayload = {
    groupName: "Team A", from: "2026-08-11T12:00:00Z", until: "2026-09-10T12:00:00Z",
    members: [
      { name: "Alice", keyPrefix: "sk-clb-alice…", isCurrentKey: true, requestCount: 10, totalTokens: 1250, cachedInputTokens: 200, totalCostUsd: 0.5, dailyUsage: [
        { date: "2026-08-11", totalTokens: 0, totalCostUsd: 0 },
        { date: "2026-08-12", totalTokens: 1250, totalCostUsd: 0.5 },
      ] },
      { name: "Bob", keyPrefix: "sk-clb-bob…", isCurrentKey: false, requestCount: 20, totalTokens: 2500, cachedInputTokens: 400, totalCostUsd: 1, dailyUsage: [
        { date: "2026-08-11", totalTokens: 2500, totalCostUsd: 1 },
        { date: "2026-08-12", totalTokens: 0, totalCostUsd: 0 },
      ] },
    ],
  };

  it("loads group members only on tab entry and refreshes current membership", async () => {
    mockDashboard();
    let calls = 0;
    server.use(http.get("/api/key-dashboard/group", ({ request }) => {
      calls += 1;
      expect(request.headers.get("Authorization")).toBe(`Bearer ${TEST_KEY}`);
      expect(request.credentials).toBe("omit");
      expect(new URL(request.url).search).toBe("");
      return HttpResponse.json(calls === 1 ? groupPayload : { ...groupPayload, groupName: null, members: [] });
    }));
    const user = userEvent.setup();
    renderWithProviders(<App />);
    await connect(user);
    expect(calls).toBe(0);
    await user.click(screen.getByRole("tab", { name: "Group keys" }));
    expect(await screen.findByRole("heading", { name: "Team A" })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Group member usage for the last 30 days" });
    expect(within(table).getByText("Alice")).toBeInTheDocument();
    expect(within(table).getByText("Bob")).toBeInTheDocument();
    expect(within(table).getByText("You")).toBeInTheDocument();
    expect(within(table).getByText("1,250")).toBeInTheDocument();
    expect(screen.getByText("3.75K")).toBeInTheDocument();
    expect(screen.getByText("Last 30 days")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(TEST_KEY);
    expect(await screen.findByRole("heading", { name: "Daily usage by key" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Tokens" })).toBeChecked();
    await user.click(screen.getByText("View daily data"));
    const tokenTable = await screen.findByRole("table", { name: "Daily Tokens by key" });
    expect(within(tokenTable).getByRole("row", { name: "2026-08-11 0 2,500" })).toBeInTheDocument();
    expect(within(tokenTable).getByRole("row", { name: "2026-08-12 1,250 0" })).toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: "Cost (USD)" }));
    const costTable = screen.getByRole("table", { name: "Daily Cost (USD) by key" });
    expect(within(costTable).getByRole("row", { name: "2026-08-11 $0.00 $1.00" })).toBeInTheDocument();
    expect(within(costTable).getByRole("row", { name: "2026-08-12 $0.50 $0.00" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Alice · sk-clb-alice…" }));
    expect(within(costTable).queryByRole("columnheader", { name: "Alice · sk-clb-alice…" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Bob · sk-clb-bob…" }));
    expect(screen.getByText("Select a key to display its daily usage.")).toBeInTheDocument();
    expect(calls).toBe(1);
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByText("No key group yet")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Daily usage by key" })).not.toBeInTheDocument();
    expect(screen.queryByText("Bob")).not.toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("retries group failures and clears remembered credentials after group 401", async () => {
    mockDashboard();
    let status = 500;
    server.use(http.get("/api/key-dashboard/group", () => status === 200
      ? HttpResponse.json(groupPayload)
      : HttpResponse.json({ error: { code: "failed", message: "Group unavailable" } }, { status })));
    const user = userEvent.setup();
    renderWithProviders(<App />);
    await user.click(await screen.findByRole("checkbox", { name: /Remember on this browser/ }));
    await connect(user);
    await user.click(screen.getByRole("tab", { name: "Group keys" }));
    expect(await screen.findByText("Group unavailable")).toBeInTheDocument();
    status = 200;
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Bob")).toBeInTheDocument();
    status = 401;
    await user.click(screen.getByRole("button", { name: "Refresh" }));
    expect(await screen.findByRole("button", { name: "Open dashboard" })).toBeInTheDocument();
    expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();
    expect(screen.queryByText("Bob")).not.toBeInTheDocument();
  });

  it.each(["tab", "disconnect"])("discards a late group response after %s", async (action) => {
    mockDashboard();
    let resolveResponse!: () => void;
    const pending = new Promise<void>((resolve) => { resolveResponse = resolve; });
    let started = false;
    server.use(http.get("/api/key-dashboard/group", async () => {
      started = true;
      await pending;
      return HttpResponse.json(groupPayload);
    }));
    const user = userEvent.setup();
    renderWithProviders(<App />);
    await connect(user);
    await user.click(screen.getByRole("tab", { name: "Group keys" }));
    await waitFor(() => expect(started).toBe(true));
    await user.click(action === "tab"
      ? screen.getByRole("tab", { name: "Overview" })
      : screen.getByRole("button", { name: "Disconnect" }));
    await act(async () => { resolveResponse(); await pending; });
    expect(screen.queryByText("Bob")).not.toBeInTheDocument();
    expect(action === "tab"
      ? screen.getByRole("tab", { name: "Overview" })
      : screen.getByRole("button", { name: "Open dashboard" })).toBeInTheDocument();
  });

  it.each([null, "gpt-5.6-sol"])("renders unrestricted or enforced models and missing lifecycle dates (%s)", async (model) => {
    mockDashboard();
    server.use(http.get("/api/key-dashboard/profile", () => HttpResponse.json({
      ...safeProfile, allowedModels: null, enforcedModel: model, expiresAt: null, lastUsedAt: null,
    })));
    const user = userEvent.setup();
    renderWithProviders(<App />);
    await connect(user);
    expect(screen.getByText(model ?? "All models")).toBeInTheDocument();
    expect(screen.getByText("Never")).toBeInTheDocument();
    expect(screen.getByText("Not used yet")).toBeInTheDocument();
    screen.getByRole("tab", { name: "Overview" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Group keys" })).toHaveFocus();
    expect(await screen.findByText("No key group yet")).toBeInTheDocument();
  });

  it("supports keyboard platform selection and shows setup guidance outside the preview", async () => {
    mockDashboard();
    server.use(http.get("/api/key-dashboard/install-script", ({ request }) => {
      const platform = new URL(request.url).searchParams.get("platform");
      return HttpResponse.text(`# ${platform}\n${TEST_KEY}\n`);
    }));
    const user = userEvent.setup();
    renderWithProviders(<App />);
    await connect(user);
    await user.click(screen.getByRole("tab", { name: "Install" }));
    await screen.findByRole("button", { name: "Copy command" });

    const group = screen.getByRole("group", { name: "Operating system" });
    const macos = within(group).getByRole("radio", { name: "macOS" });
    const linux = within(group).getByRole("radio", { name: "Linux" });
    const windows = within(group).getByRole("radio", { name: "Windows" });
    macos.focus();
    expect(macos).toBeChecked();
    await user.keyboard("{ArrowRight}");
    expect(linux).toHaveFocus();
    expect(linux).toBeChecked();
    expect(await screen.findByText("codex-lb-linux.sh", { exact: true })).toBeInTheDocument();
    await user.keyboard("{ArrowRight}");
    expect(windows).toHaveFocus();
    expect(windows).toBeChecked();
    expect(await screen.findByText("codex-lb-windows.ps1", { exact: true })).toBeInTheDocument();
    await user.tab();
    expect(screen.getByRole("checkbox", { name: "Keep Codex account login session" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("button", { name: "Copy command" })).toHaveFocus();
    const follows = (first: Element, second: Element) =>
      Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);
    const prerequisite = screen.getByRole("region", { name: "Before you run" });
    expect(within(prerequisite).getByText(/Install the Codex client first/)).toBeVisible();
    expect(screen.getByText("Works with Codex App, Codex CLI and the IDE extension.")).toBeVisible();
    const optionsStep = screen.getByRole("heading", { name: "Setup options" });
    const commandStep = screen.getByRole("heading", { name: "Run in your terminal" });
    const otherWays = screen.getByRole("heading", { name: "Other ways to set up" });
    expect(follows(prerequisite, group)).toBe(true);
    expect(follows(group, optionsStep)).toBe(true);
    expect(follows(optionsStep, commandStep)).toBe(true);
    expect(follows(commandStep, otherWays)).toBe(true);
    expect(follows(otherWays, screen.getByRole("heading", { name: "Prefer a script file?" }))).toBe(true);
    const guidance = screen.getByRole("complementary", { name: "Good to know" });
    expect(within(guidance).getByText(/Backs up and replaces/)).toBeVisible();
    expect(within(guidance).getByText(/commands may remain in shell history/)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Restore previous setup" })).toBeVisible();
    expect(screen.getByText(/Restores the files saved before the first install with uninstall support/)).toBeVisible();
    expect(screen.getByText(/-File \(Join-Path \$codexDir 'codex-lb-uninstall.ps1'\)/)).toBeVisible();
    const preview = screen.getByText("Preview script", { selector: "summary" });
    expect(preview.closest("details")).not.toHaveAttribute("open");
    await user.click(preview);
    expect(preview.closest("details")).toHaveAttribute("open");
    expect(document.body.textContent).not.toContain(TEST_KEY);
  });

  it.each(["http:", "https:"])("exports the logged-in key over %s while masking previews and omitting cookies", async (protocol) => {
    vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      protocol,
      origin: `${protocol}//localhost:2455`,
    });
    mockDashboard();
    const requests: string[] = [];
    server.use(http.get("/api/key-dashboard/install-script", ({ request }) => {
      expect(request.headers.get("Authorization")).toBe(`Bearer ${TEST_KEY}`);
      expect(request.credentials).toBe("omit");
      expect(request.cache).toBe("no-store");
      expect(request.url).not.toContain(TEST_KEY);
      expect(new URL(request.url).searchParams.get("scheme")).toBe(protocol === "https:" ? "https" : null);
      expect(new URL(request.url).searchParams.get("keep_login")).toBeNull();
      const platform = new URL(request.url).searchParams.get("platform");
      requests.push(platform!);
      return HttpResponse.text(`# ${platform}\n${TEST_KEY}\n`);
    }));
    const user = userEvent.setup();
    const clipboard = vi.spyOn(navigator.clipboard, "writeText");
    vi.stubGlobal("isSecureContext", true);
    const createObjectURL = vi.fn<(blob: Blob) => string>(() => "blob:installer");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", class extends URL {
      static createObjectURL = createObjectURL;
      static revokeObjectURL = revokeObjectURL;
    });
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    renderWithProviders(<App />);
    await connect(user);
    expect(requests).toHaveLength(0);
    await user.click(screen.getByRole("tab", { name: "Install" }));
    expect(screen.queryByRole("heading", { name: "Recent requests" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Keep Codex account login session" }));
    expect(screen.queryByText(/CẢNH BÁO/)).not.toBeInTheDocument();
    for (const [platform, label] of [["macos", "macOS"], ["linux", "Linux"], ["windows", "Windows"]]) {
      await user.click(screen.getByRole("radio", { name: label }));
      await user.click(await screen.findByRole("button", { name: "Copy script" }));
      expect(screen.getByText(`codex-lb-${platform}.${platform === "windows" ? "ps1" : "sh"}`, { exact: true })).toBeInTheDocument();
      expect(screen.getByText(platform === "windows" ? "PowerShell" : "Bash", { selector: "span:not([aria-hidden])", exact: true })).toBeInTheDocument();
      expect(clipboard).toHaveBeenLastCalledWith(`# ${platform}\n${TEST_KEY}\n`);
      expect(document.body.textContent).not.toContain(TEST_KEY);
      await user.click(screen.getByRole("button", { name: "Copy command" }));
      const command = clipboard.mock.calls.at(-1)![0];
      expect(command).toContain(`Authorization: Bearer ${TEST_KEY}`);
      expect(command).toContain(`platform=${platform}`);
      expect(command.includes("scheme=https")).toBe(protocol === "https:");
      expect(command).toContain(platform === "windows" ? "curl.exe" : "curl -fsS");
      await user.click(screen.getByRole("button", { name: "Copy uninstall command" }));
      const uninstall = clipboard.mock.calls.at(-1)![0];
      expect(uninstall).toContain(`codex-lb-uninstall.${platform === "windows" ? "ps1" : "sh"}`);
      expect(uninstall).not.toContain(TEST_KEY);
      await user.click(screen.getByRole("button", { name: "Download script" }));
      expect(anchorClick.mock.instances.at(-1)).toHaveAttribute("download", `codex-lb-${platform}.${platform === "windows" ? "ps1" : "sh"}`);
      const blob = createObjectURL.mock.calls.at(-1)![0] as Blob;
      const content = await new Promise<string>((resolve) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.readAsText(blob);
      });
      expect(content).toBe(`# ${platform}\n${TEST_KEY}\n`);
    }
    expect(requests).toEqual(["macos", "linux", "windows"]);
    expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();
    await user.click(screen.getByRole("tab", { name: "Overview" }));
    expect(await screen.findByRole("heading", { name: "Production client" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy script" })).not.toBeInTheDocument();
  });

  it("defaults to keep-login exports behind a highlighted Vietnamese confirmation", async () => {
    mockDashboard();
    const keepLogin: (string | null)[] = [];
    server.use(http.get("/api/key-dashboard/install-script", ({ request }) => {
      keepLogin.push(new URL(request.url).searchParams.get("keep_login"));
      return HttpResponse.text(`# keep-login\n${TEST_KEY}\n`);
    }));
    const user = userEvent.setup();
    const clipboard = vi.spyOn(navigator.clipboard, "writeText");
    vi.stubGlobal("isSecureContext", true);
    const anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    vi.stubGlobal("URL", class extends URL {
      static createObjectURL = vi.fn(() => "blob:installer");
      static revokeObjectURL = vi.fn();
    });
    renderWithProviders(<App />);
    await connect(user);
    await user.click(screen.getByRole("tab", { name: "Install" }));

    expect(screen.getByRole("checkbox", { name: "Keep Codex account login session" })).toBeChecked();
    expect(screen.getByRole("note")).toHaveTextContent("CẢNH BÁO: Access token đăng nhập sẽ được gửi lên server");
    await user.click(await screen.findByRole("button", { name: "Copy script" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Xác nhận gửi access token lên server" });
    expect(within(dialog).getByText(/gửi kèm access token đăng nhập lên server codex-lb/)).toBeVisible();
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(clipboard).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Copy command" }));
    await confirmKeepLoginExport(user);
    await waitFor(() => expect(clipboard).toHaveBeenCalledTimes(1));
    expect(clipboard.mock.calls[0][0]).toContain("keep_login=true");

    await user.click(screen.getByRole("button", { name: "Download script" }));
    expect(anchorClick).not.toHaveBeenCalled();
    await confirmKeepLoginExport(user);
    await waitFor(() => expect(anchorClick).toHaveBeenCalledTimes(1));
    expect(keepLogin.every((value) => value === "true")).toBe(true);
    expect(document.body.textContent).not.toContain(TEST_KEY);
  });

  it("handles installer failures and invalid credentials without administrator authentication", async () => {
    mockDashboard();
    let status = 500;
    const adminAuth = vi.fn();
    server.use(
      http.get("/api/dashboard-auth/session", adminAuth),
      http.get("/api/key-dashboard/install-script", () => HttpResponse.json({ error: { message: "failed" } }, { status })),
    );
    const user = userEvent.setup();
    renderWithProviders(<App />);
    await connect(user);
    await user.click(screen.getByRole("tab", { name: "Install" }));
    expect(await screen.findByText("Could not load the setup script. Please try again.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Copy script" })).not.toBeInTheDocument();
    status = 401;
    await user.click(screen.getAllByRole("button", { name: "Refresh" }).at(-1)!);
    expect(await screen.findByRole("button", { name: "Open dashboard" })).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Install" })).not.toBeInTheDocument();
    expect(adminAuth).not.toHaveBeenCalled();
  });

  it("discards stale platform responses and exports only the new key after reconnecting", async () => {
    mockDashboard();
    let release: () => void = () => {};
    const delayed = new Promise<void>((resolve) => { release = resolve; });
    server.use(http.get("/api/key-dashboard/install-script", async ({ request }) => {
      const platform = new URL(request.url).searchParams.get("platform");
      const key = request.headers.get("Authorization")!.slice(7);
      if (platform === "macos" && key === TEST_KEY) await delayed;
      return HttpResponse.text(`# ${platform}\n${key}\n`);
    }));
    const user = userEvent.setup();
    const clipboard = vi.spyOn(navigator.clipboard, "writeText");
    vi.stubGlobal("isSecureContext", true);
    renderWithProviders(<App />);
    await connect(user);
    await user.click(screen.getByRole("tab", { name: "Install" }));
    await user.click(screen.getByRole("radio", { name: "Linux" }));
    await user.click(await screen.findByRole("button", { name: "Copy script" }));
    await confirmKeepLoginExport(user);
    await waitFor(() => expect(clipboard).toHaveBeenLastCalledWith(`# linux\n${TEST_KEY}\n`));
    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    release();
    await connect(user, "sk-clb-new-key");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    await user.click(screen.getByRole("tab", { name: "Install" }));
    await user.click(await screen.findByRole("button", { name: "Copy script" }));
    await confirmKeepLoginExport(user);
    await waitFor(() => expect(clipboard).toHaveBeenLastCalledWith("# macos\nsk-clb-new-key\n"));
    expect(document.body.textContent).not.toContain(TEST_KEY);
  });

  it("remembers a valid key only after opt-in and restores it on the next mount", async () => {
    let profileCalls = 0;
    server.use(
      http.get("/api/key-dashboard/profile", ({ request }) => {
        profileCalls += 1;
        expect(request.headers.get("Authorization")).toBe(`Bearer ${TEST_KEY}`);
        return HttpResponse.json(safeProfile);
      }),
      http.get("/v1/usage", () => HttpResponse.json(usagePayload)),
      http.get("/api/key-dashboard/request-logs", () =>
        HttpResponse.json({ requests: [safeLog], total: 1, hasMore: false }),
      ),
    );
    const user = userEvent.setup();
    const firstRender = renderWithProviders(<App />);

    await user.click(await screen.findByRole("checkbox", { name: /Remember on this browser/ }));
    await user.type(screen.getByLabelText("API key"), TEST_KEY);
    await user.click(screen.getByRole("button", { name: "Open dashboard" }));

    expect(await screen.findByRole("heading", { name: "Production client" })).toBeInTheDocument();
    expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBe(TEST_KEY);

    firstRender.unmount();
    renderWithProviders(<App />);

    expect(await screen.findByRole("heading", { name: "Production client" })).toBeInTheDocument();
    await waitFor(() => expect(profileCalls).toBe(2));
    await user.click(screen.getByRole("button", { name: "Disconnect" }));
    expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();
  });

  it("returns to key entry with an independent invalid-key error", async () => {
    window.localStorage.setItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY, TEST_KEY);
    server.use(
      http.get("/api/key-dashboard/profile", () =>
        HttpResponse.json(
          { error: { code: "invalid_api_key", message: "Invalid API key" } },
          { status: 401 },
        ),
      ),
      http.get("/v1/usage", () =>
        HttpResponse.json(
          { error: { code: "invalid_api_key", message: "Invalid API key" } },
          { status: 401 },
        ),
      ),
      http.get("/api/key-dashboard/request-logs", () =>
        HttpResponse.json(
          { error: { code: "invalid_api_key", message: "Invalid API key" } },
          { status: 401 },
        ),
      ),
    );
    renderWithProviders(<App />);

    expect(await screen.findByText("This API key is invalid, inactive, or expired.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText("API key")).toHaveValue(""));
    expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();
  });

  describe("automatic refresh", () => {
    let visibility: DocumentVisibilityState = "visible";

    beforeEach(() => {
      visibility = "visible";
      vi.spyOn(document, "visibilityState", "get").mockImplementation(() => visibility);
      vi.useFakeTimers({ shouldAdvanceTime: true });
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    const setupUser = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    const tick = (ms = 30_000) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

    function countDashboard(overrides: { usage?: () => Response | Promise<Response> } = {}) {
      const calls = { profile: 0, usage: 0, logs: [] as string[] };
      server.use(
        http.get("/api/key-dashboard/profile", () => { calls.profile += 1; return HttpResponse.json(safeProfile); }),
        http.get("/v1/usage", () => {
          calls.usage += 1;
          return overrides.usage?.() ?? HttpResponse.json({ ...usagePayload, request_count: calls.usage === 1 ? 9 : 777 });
        }),
        http.get("/api/key-dashboard/request-logs", ({ request }) => {
          const offset = new URL(request.url).searchParams.get("offset") ?? "0";
          calls.logs.push(offset);
          return HttpResponse.json({
            requests: [{ ...safeLog, requestId: `req-${offset}`, model: offset === "0" ? "gpt-first-page" : "gpt-second-page" }],
            total: 40,
            hasMore: offset === "0",
          });
        }),
      );
      return calls;
    }

    it("refreshes the visible Overview silently every 30 seconds", async () => {
      const calls = countDashboard();
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      expect(screen.getByText("9")).toBeInTheDocument();
      await tick();
      expect(await screen.findByText("777")).toBeInTheDocument();
      expect(calls).toEqual({ profile: 2, usage: 2, logs: ["0", "0"] });
      expect(screen.getByRole("button", { name: "Refresh" })).toBeEnabled();
    });

    it("pauses while hidden and refreshes once when visible again", async () => {
      const calls = countDashboard();
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      visibility = "hidden";
      document.dispatchEvent(new Event("visibilitychange"));
      await tick(90_000);
      expect(calls.usage).toBe(1);
      visibility = "visible";
      await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
      await waitFor(() => expect(calls.usage).toBe(2));
      await tick(1_000);
      expect(calls.usage).toBe(2);
    });

    it("keeps a later request-log page while refreshing usage", async () => {
      const calls = countDashboard();
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      await user.click(screen.getByRole("button", { name: "Next page" }));
      expect(await screen.findByText(/gpt-second-page/)).toBeInTheDocument();
      expect(calls.logs).toEqual(["0", "25"]);
      await tick();
      expect(await screen.findByText("777")).toBeInTheDocument();
      expect(calls.logs).toEqual(["0", "25"]);
      expect(screen.getByText(/gpt-second-page/)).toBeInTheDocument();
    });

    it("keeps data on background failures and disconnects on 401", async () => {
      let status = 200;
      const calls = countDashboard({
        usage: () => status === 200
          ? HttpResponse.json({ ...usagePayload, request_count: 777 })
          : HttpResponse.json({ error: { code: "failed", message: "Usage unavailable" } }, { status }),
      });
      const user = setupUser();
      renderWithProviders(<App />);
      await user.click(await screen.findByRole("checkbox", { name: /Remember on this browser/ }));
      await connect(user);
      status = 500;
      await tick();
      expect(await screen.findByText("Usage unavailable")).toBeInTheDocument();
      expect(screen.getByText("777")).toBeInTheDocument();
      status = 200;
      await tick();
      await waitFor(() => expect(screen.queryByText("Usage unavailable")).not.toBeInTheDocument());
      status = 401;
      await tick();
      expect(await screen.findByRole("button", { name: "Open dashboard" })).toBeInTheDocument();
      expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();
      expect(calls.usage).toBe(4);
    });

    it("does not overlap a pending refresh and lets a manual refresh win", async () => {
      let release!: () => void;
      let hold = false;
      const calls = countDashboard({
        usage: async () => {
          if (hold) await new Promise<void>((resolve) => { release = resolve; });
          return HttpResponse.json({ ...usagePayload, request_count: hold ? 111 : 222 });
        },
      });
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      hold = true;
      await tick();
      await waitFor(() => expect(calls.usage).toBe(2));
      await tick();
      expect(calls.usage).toBe(2);
      hold = false;
      await user.click(screen.getByRole("button", { name: "Refresh" }));
      expect(await screen.findByText("222")).toBeInTheDocument();
      await act(async () => { release(); });
      await tick(1_000);
      expect(screen.getByText("222")).toBeInTheDocument();
      expect(screen.queryByText("111")).not.toBeInTheDocument();
    });

    it("discards a pending automatic refresh after disconnect", async () => {
      let release!: () => void;
      let hold = false;
      const calls = countDashboard({
        usage: async () => {
          if (hold) await new Promise<void>((resolve) => { release = resolve; });
          return HttpResponse.json(usagePayload);
        },
      });
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      hold = true;
      await tick();
      await waitFor(() => expect(calls.usage).toBe(2));
      await user.click(screen.getByRole("button", { name: "Disconnect" }));
      await act(async () => { release(); });
      await tick(1_000);
      expect(screen.getByRole("button", { name: "Open dashboard" })).toBeInTheDocument();
      expect(screen.queryByRole("tab", { name: "Overview" })).not.toBeInTheDocument();
    });

    it("refreshes group usage without losing chart choices or overlapping", async () => {
      countDashboard();
      let groupCalls = 0;
      let status = 200;
      let release: (() => void) | null = null;
      let hold = false;
      server.use(http.get("/api/key-dashboard/group", async () => {
        groupCalls += 1;
        if (hold) await new Promise<void>((resolve) => { release = resolve; });
        if (status !== 200) return HttpResponse.json({ error: { code: "failed", message: "Group unavailable" } }, { status });
        if (groupCalls === 1) return HttpResponse.json(groupPayload);
        const [alice, bob] = groupPayload.members;
        return HttpResponse.json({ ...groupPayload, members: [{ ...bob, requestCount: 70 }, alice] });
      }));
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      await user.click(screen.getByRole("tab", { name: "Group keys" }));
      expect(await screen.findByRole("heading", { name: "Daily usage by key" })).toBeInTheDocument();
      await user.click(screen.getByRole("checkbox", { name: "Bob · sk-clb-bob…" }));
      await tick();
      const table = screen.getByRole("table", { name: "Group member usage for the last 30 days" });
      expect(await within(table).findByText("70")).toBeInTheDocument();
      expect(screen.getByRole("checkbox", { name: "Bob · sk-clb-bob…" })).not.toBeChecked();
      expect(screen.getByRole("checkbox", { name: "Alice · sk-clb-alice…" })).toBeChecked();
      status = 500;
      await tick();
      expect(await screen.findByText("Group unavailable")).toBeInTheDocument();
      expect(within(table).getByText("70")).toBeInTheDocument();
      status = 200;
      hold = true;
      await tick();
      await waitFor(() => expect(groupCalls).toBe(4));
      await tick();
      expect(groupCalls).toBe(4);
      hold = false;
      await act(async () => { release?.(); });
      await waitFor(() => expect(screen.queryByText("Group unavailable")).not.toBeInTheDocument());
      expect(within(table).getByText("70")).toBeInTheDocument();
    });

    it("shows background group failures for an ungrouped key", async () => {
      countDashboard();
      let status = 200;
      server.use(http.get("/api/key-dashboard/group", () => status === 200
        ? HttpResponse.json({ groupName: null, from: "2026-08-11T12:00:00Z", until: "2026-09-10T12:00:00Z", members: [] })
        : HttpResponse.json({ error: { code: "failed", message: "Group unavailable" } }, { status })));
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      await user.click(screen.getByRole("tab", { name: "Group keys" }));
      expect(await screen.findByText("No key group yet")).toBeInTheDocument();
      status = 500;
      await tick();
      expect(await screen.findByText("Group unavailable")).toBeInTheDocument();
      expect(screen.getByText("No key group yet")).toBeInTheDocument();
    });

    it("disconnects on a 401 even when another refresh request fails first", async () => {
      let failing = false;
      countDashboard({
        usage: () => failing
          ? HttpResponse.json({ error: { code: "failed", message: "Usage unavailable" } }, { status: 500 })
          : HttpResponse.json(usagePayload),
      });
      server.use(http.get("/api/key-dashboard/profile", async () => {
        if (!failing) return HttpResponse.json(safeProfile);
        await new Promise((resolve) => setTimeout(resolve, 50));
        return HttpResponse.json({ error: { code: "invalid_api_key", message: "Invalid key" } }, { status: 401 });
      }));
      server.use(http.get("/api/key-dashboard/request-logs", async () => {
        // A request that never settles must not hold back the 401.
        if (failing) await new Promise(() => {});
        return HttpResponse.json({ requests: [], total: 0, hasMore: false });
      }));
      const user = setupUser();
      renderWithProviders(<App />);
      await user.click(await screen.findByRole("checkbox", { name: /Remember on this browser/ }));
      await connect(user);
      failing = true;
      await tick();
      await tick(100);
      expect(await screen.findByRole("button", { name: "Open dashboard" })).toBeInTheDocument();
      expect(window.localStorage.getItem(KEY_DASHBOARD_API_KEY_STORAGE_KEY)).toBeNull();
    });

    it("shows a background failure while a sibling request hangs and keeps refreshing", async () => {
      let failing = false;
      const calls = countDashboard({
        usage: () => failing
          ? HttpResponse.json({ error: { code: "failed", message: "Usage unavailable" } }, { status: 500 })
          : HttpResponse.json(usagePayload),
      });
      server.use(http.get("/api/key-dashboard/request-logs", async () => {
        if (failing) await new Promise(() => {});
        return HttpResponse.json({ requests: [], total: 0, hasMore: false });
      }));
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      failing = true;
      await tick();
      expect(await screen.findByText("Usage unavailable")).toBeInTheDocument();
      failing = false;
      await tick();
      await waitFor(() => expect(screen.queryByText("Usage unavailable")).not.toBeInTheDocument());
      expect(calls.usage).toBe(3);
    });

    it("clears a background refresh error on disconnect", async () => {
      let failing = false;
      countDashboard({
        usage: () => failing
          ? HttpResponse.json({ error: { code: "failed", message: "Usage unavailable" } }, { status: 500 })
          : HttpResponse.json(usagePayload),
      });
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      failing = true;
      await tick();
      expect(await screen.findByText("Usage unavailable")).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Disconnect" }));
      expect(await screen.findByRole("button", { name: "Open dashboard" })).toBeInTheDocument();
      expect(screen.queryByText("Usage unavailable")).not.toBeInTheDocument();
    });

    it("never refreshes the Install tab automatically", async () => {
      const calls = countDashboard();
      let installCalls = 0;
      let groupCalls = 0;
      server.use(
        http.get("/api/key-dashboard/install-script", () => { installCalls += 1; return new HttpResponse("#!/bin/bash\n"); }),
        http.get("/api/key-dashboard/group", () => { groupCalls += 1; return HttpResponse.json(groupPayload); }),
      );
      const user = setupUser();
      renderWithProviders(<App />);
      await connect(user);
      await user.click(screen.getByRole("tab", { name: "Install" }));
      await waitFor(() => expect(installCalls).toBe(1));
      await tick(90_000);
      expect(installCalls).toBe(1);
      expect(groupCalls).toBe(0);
      expect(calls).toEqual({ profile: 1, usage: 1, logs: ["0"] });
    });
  });
});
