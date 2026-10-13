import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import { RoutingSettings } from "@/features/settings/components/routing-settings";
import { useSettings } from "@/features/settings/hooks/use-settings";
import { SettingsUpdateRequestSchema, type SettingsUpdateRequest } from "@/features/settings/schemas";
import { createDashboardSettings } from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

// Exercise the real settings query, mutation, payload builder, API parser and routing UI.
function RoutingSettingsWithQuery() {
  const { settingsQuery, updateSettingsMutation } = useSettings();
  if (!settingsQuery.data) return <p>Loading settings</p>;
  return (
    <>
      {updateSettingsMutation.error && <p role="alert">{updateSettingsMutation.error.message}</p>}
      <RoutingSettings
        settings={settingsQuery.data}
        busy={updateSettingsMutation.isPending}
        onSave={async (payload) => {
          await updateSettingsMutation.mutateAsync(payload);
        }}
      />
    </>
  );
}

const picker = () => screen.getByRole("combobox", { name: "Subscription model" });
const saveButton = () => screen.getByRole("button", { name: "Save model plans" });

function mockNativeModel() {
  server.use(
    http.get("/api/models", () =>
      HttpResponse.json({
        models: [{ id: "gpt-6-luna", name: "GPT 6 Luna" }],
      }),
    ),
  );
}

describe("subscription model-plan routing settings flow", () => {
  it("adds, edits, preserves on unrelated save, and removes a policy through the settings API", async () => {
    let settings = createDashboardSettings({ version: 7, modelPlanRoutingPolicies: {}, stickyThreadsEnabled: false });
    const requests: SettingsUpdateRequest[] = [];
    server.use(
      http.get("/api/settings", () => HttpResponse.json(settings)),
      http.put("/api/settings", async ({ request }) => {
        const payload = SettingsUpdateRequestSchema.parse(await request.json());
        requests.push(payload);
        settings = {
          ...settings,
          modelPlanRoutingPolicies: payload.modelPlanRoutingPolicies ?? settings.modelPlanRoutingPolicies,
          stickyThreadsEnabled: payload.stickyThreadsEnabled ?? settings.stickyThreadsEnabled,
          version: settings.version! + 1,
        };
        return HttpResponse.json(settings);
      }),
    );
    mockNativeModel();
    const user = userEvent.setup();
    renderWithProviders(<RoutingSettingsWithQuery />);
    await screen.findByRole("region", { name: "Subscription model plans" });
    await waitFor(() => expect(picker()).toBeEnabled());
    await user.click(picker());
    await user.click(screen.getByRole("option", { name: "gpt-6-luna" }));
    await user.click(saveButton());
    await waitFor(() => expect(screen.getByRole("button", { name: "Edit plans for gpt-6-luna" })).toBeEnabled());
    expect(requests[0]).toMatchObject({ expectedVersion: 7, modelPlanRoutingPolicies: { "gpt-6-luna": ["free"] } });

    await user.click(screen.getByRole("button", { name: "Edit plans for gpt-6-luna" }));
    await user.click(screen.getByRole("checkbox", { name: "plus" }));
    await user.click(saveButton());
    await waitFor(() => expect(screen.getByText("free, plus")).toBeInTheDocument());
    await waitFor(() => expect(picker()).toBeEnabled());
    expect(requests[1]).toMatchObject({
      expectedVersion: 8,
      modelPlanRoutingPolicies: { "gpt-6-luna": ["free", "plus"] },
    });

    await user.click(screen.getByRole("switch", { name: "Enable sticky threads" }));
    await waitFor(() => expect(screen.getByRole("switch", { name: "Enable sticky threads" })).toBeChecked());
    await waitFor(() => expect(picker()).toBeEnabled());
    expect(requests[2]).toMatchObject({
      expectedVersion: 9,
      stickyThreadsEnabled: true,
      modelPlanRoutingPolicies: { "gpt-6-luna": ["free", "plus"] },
    });
    expect(screen.getByText("free, plus")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove plans for gpt-6-luna" }));
    await screen.findByText("No restrictions configured.");
    expect(requests[3]).toMatchObject({ expectedVersion: 10, modelPlanRoutingPolicies: {} });
    expect(screen.queryByRole("button", { name: "Edit plans for gpt-6-luna" })).not.toBeInTheDocument();
    expect(saveButton()).toBeDisabled();
  });

  it.each([false, true])(
    "stays busy until %s conflict/success refetch settles and uses fresh policies/version",
    async (conflict) => {
      let settings = createDashboardSettings({ version: 7, modelPlanRoutingPolicies: { "retired-native": ["free"] } });
      const requests: SettingsUpdateRequest[] = [];
      let startRefetch!: () => void;
      const refetchStarted = new Promise<void>((resolve) => {
        startRefetch = resolve;
      });
      let releaseRefetch!: () => void;
      const refetchReleased = new Promise<void>((resolve) => {
        releaseRefetch = resolve;
      });
      let reads = 0;
      server.use(
        http.get("/api/settings", async () => {
          if (++reads === 2) {
            startRefetch();
            await refetchReleased;
          }
          return HttpResponse.json(settings);
        }),
        http.put("/api/settings", async ({ request }) => {
          const payload = SettingsUpdateRequestSchema.parse(await request.json());
          requests.push(payload);
          settings = {
            ...settings,
            version: settings.version! + 1,
            modelPlanRoutingPolicies:
              requests.length === 1
                ? { "retired-native": conflict ? ["team"] : ["free", "plus"], "another-model": ["free"] }
                : (payload.modelPlanRoutingPolicies ?? {}),
          };
          if (conflict && requests.length === 1) {
            return HttpResponse.json(
              { error: { code: "settings_conflict", message: "Settings changed; retry after refresh." } },
              { status: 409 },
            );
          }
          return HttpResponse.json(settings);
        }),
      );
      mockNativeModel();
      const user = userEvent.setup();
      renderWithProviders(<RoutingSettingsWithQuery />);
      await user.click(await screen.findByRole("button", { name: "Edit plans for retired-native" }));
      await user.click(screen.getByRole("checkbox", { name: "plus" }));
      await user.click(saveButton());
      await refetchStarted;
      try {
        await waitFor(() => expect(saveButton()).toBeDisabled());
        expect(picker()).toBeDisabled();
        expect(screen.getByRole("button", { name: "Remove plans for retired-native" })).toBeDisabled();
      } finally {
        releaseRefetch();
      }
      await waitFor(() => expect(picker()).toBeEnabled());
      expect(saveButton()).toBeDisabled();
      expect(picker()).toHaveTextContent("Subscription model");
      if (conflict) expect(screen.getByRole("alert")).toHaveTextContent("Settings changed");
      const row = screen.getByRole("button", { name: "Edit plans for retired-native" }).parentElement!;
      expect(within(row).getByText(conflict ? "team" : "free, plus")).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Edit plans for retired-native" }));
      expect(screen.getByRole("checkbox", { name: conflict ? "team" : "plus" })).toBeChecked();
      await user.click(screen.getByRole("checkbox", { name: "edu" }));
      await user.click(saveButton());
      await waitFor(() => expect(picker()).toBeEnabled());
      expect(requests[1]).toMatchObject({
        expectedVersion: 8,
        modelPlanRoutingPolicies: {
          "retired-native": conflict ? ["team", "edu"] : ["free", "plus", "edu"],
          "another-model": ["free"],
        },
      });
    },
  );
});
