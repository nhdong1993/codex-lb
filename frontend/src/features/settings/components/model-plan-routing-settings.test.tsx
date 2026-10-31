import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { describe, expect, it, vi } from "vitest";

import { ModelPlanRoutingSettings } from "@/features/settings/components/model-plan-routing-settings";
import type { ModelPlanRoutingPolicies } from "@/features/settings/schemas";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

const EXAMPLE_MODELS = ["gpt-5.6-terra", "gpt-5.6-luna", "gpt-6-luna"];
const picker = () => screen.getByRole("combobox", { name: "Subscription model" });
const saveButton = () => screen.getByRole("button", { name: "Save model plans" });

function renderEditor(policies: ModelPlanRoutingPolicies = {}, busy = false) {
  const onSave = vi.fn().mockResolvedValue(undefined);
  const view = renderWithProviders(<ModelPlanRoutingSettings policies={policies} busy={busy} onSave={onSave} />);
  return { ...view, onSave };
}

function mockCatalog() {
  server.use(
    http.get("/api/models", () =>
      HttpResponse.json({
        models: [
          ...EXAMPLE_MODELS.map((id) => ({ id, name: id })),
          { id: "source-chat", name: "Source chat", sourceOnly: true },
          { id: "native-image", name: "Image", imageOnly: true },
        ],
      }),
    ),
  );
}

describe("ModelPlanRoutingSettings", () => {
  it("offers only native non-image models plus saved catalog-missing IDs", async () => {
    mockCatalog();
    const user = userEvent.setup();
    renderEditor({ "retired-native": ["free"] });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    await user.click(picker());
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "gpt-5.6-luna",
      "gpt-5.6-terra",
      "gpt-6-luna",
      "retired-native",
    ]);
    expect(screen.queryByRole("option", { name: "source-chat" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "native-image" })).not.toBeInTheDocument();
  });

  it("keeps saved IDs the catalog now lists only as source-only or image-only selectable", async () => {
    mockCatalog();
    const user = userEvent.setup();
    const { onSave } = renderEditor({ "source-chat": ["plus"], "native-image": ["pro"] });
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    await user.click(picker());
    expect(screen.getAllByRole("option").map((option) => option.textContent)).toEqual([
      "gpt-5.6-luna",
      "gpt-5.6-terra",
      "gpt-6-luna",
      "native-image",
      "source-chat",
    ]);
    await user.click(screen.getByRole("option", { name: "source-chat" }));
    expect(screen.getByRole("checkbox", { name: "plus" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "promax" })).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "team" }));
    await user.click(saveButton());
    expect(onSave).toHaveBeenCalledWith({ "source-chat": ["plus", "team"], "native-image": ["pro"] });
  });

  it.each(EXAMPLE_MODELS)("defaults to no policy and explicitly saves %s for free", async (model) => {
    mockCatalog();
    const user = userEvent.setup();
    const { onSave } = renderEditor();
    expect(screen.getByText("No restrictions configured.")).toBeInTheDocument();
    expect(screen.getByText(/does not grant model access; there is no fallback to another plan/)).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
    expect(saveButton()).toBeDisabled();
    await waitFor(() => expect(picker()).toBeEnabled());
    await user.click(picker());
    await user.click(screen.getByRole("option", { name: model }));
    expect(screen.getByRole("checkbox", { name: "free" })).toBeChecked();
    await user.click(saveButton());
    expect(onSave).toHaveBeenCalledWith({ [model]: ["free"] });
    await waitFor(() => expect(saveButton()).toBeDisabled());
  });

  it("edits a saved missing ID without dropping other policies and blocks empty plans", async () => {
    mockCatalog();
    const user = userEvent.setup();
    const { onSave } = renderEditor({ "retired-native": ["free"], "gpt-6-luna": ["free"] });
    await user.click(screen.getByRole("button", { name: "Edit plans for retired-native" }));
    expect(picker()).toHaveTextContent("retired-native");
    await user.click(screen.getByRole("checkbox", { name: "free" }));
    expect(saveButton()).toBeDisabled();
    await user.click(saveButton());
    expect(onSave).not.toHaveBeenCalled();
    await user.click(screen.getByRole("checkbox", { name: "plus" }));
    await user.click(screen.getByRole("checkbox", { name: "prolite" }));
    await user.click(saveButton());
    expect(onSave).toHaveBeenCalledWith({ "retired-native": ["plus", "prolite"], "gpt-6-luna": ["free"] });
  });

  it("removes a missing ID and clears the last policy with an explicit empty mapping", async () => {
    const user = userEvent.setup();
    const { onSave, rerender } = renderEditor({ "retired-native": ["free"], "gpt-6-luna": ["free"] });
    await user.click(screen.getByRole("button", { name: "Remove plans for retired-native" }));
    expect(onSave).toHaveBeenLastCalledWith({ "gpt-6-luna": ["free"] });
    rerender(<ModelPlanRoutingSettings policies={{ "gpt-6-luna": ["free"] }} busy={false} onSave={onSave} />);
    await user.click(screen.getByRole("button", { name: "Remove plans for gpt-6-luna" }));
    expect(onSave).toHaveBeenLastCalledWith({});
  });

  it("announces loading and prevents selecting an unloaded catalog", async () => {
    let resolveModels!: () => void;
    const response = new Promise<void>((resolve) => {
      resolveModels = resolve;
    });
    server.use(
      http.get("/api/models", async () => {
        await response;
        return HttpResponse.json({ models: [] });
      }),
    );
    renderEditor();
    expect(screen.getByRole("status")).toHaveTextContent("Loading subscription models");
    expect(picker()).toBeDisabled();
    expect(saveButton()).toBeDisabled();
    resolveModels();
    await waitFor(() => expect(screen.queryByRole("status")).not.toBeInTheDocument());
    expect(picker()).toBeDisabled();
  });

  it("keeps saved missing policies editable and removable during catalog failure", async () => {
    server.use(
      http.get("/api/models", () =>
        HttpResponse.json({ error: { code: "catalog_unavailable", message: "Catalog unavailable" } }, { status: 503 }),
      ),
    );
    const user = userEvent.setup();
    const { onSave } = renderEditor({ "retired-native": ["free"] });
    expect(await screen.findByRole("alert")).toHaveTextContent("Saved restrictions can still be edited or removed");
    await user.click(screen.getByRole("button", { name: "Edit plans for retired-native" }));
    await user.click(screen.getByRole("checkbox", { name: "plus" }));
    await user.click(saveButton());
    expect(onSave).toHaveBeenLastCalledWith({ "retired-native": ["free", "plus"] });
    await user.click(screen.getByRole("button", { name: "Remove plans for retired-native" }));
    expect(onSave).toHaveBeenLastCalledWith({});
  });

  it("disables all editing controls while busy", () => {
    renderEditor({ "retired-native": ["free"] }, true);
    const editor = within(screen.getByRole("region", { name: "Subscription model plans" }));
    for (const control of [...editor.getAllByRole("button"), ...editor.getAllByRole("checkbox"), picker()]) {
      expect(control).toBeDisabled();
    }
  });

  it("retains a retryable draft after a failed save without an unhandled rejection", async () => {
    const user = userEvent.setup();
    const { onSave } = renderEditor({ "retired-native": ["free"] });
    onSave.mockRejectedValueOnce(new Error("Save failed"));
    await user.click(screen.getByRole("button", { name: "Edit plans for retired-native" }));
    await user.click(screen.getByRole("checkbox", { name: "plus" }));
    await user.click(saveButton());
    expect(picker()).toHaveTextContent("retired-native");
    expect(screen.getByRole("checkbox", { name: "plus" })).toBeChecked();
    expect(saveButton()).toBeEnabled();
    await user.click(saveButton());
    expect(onSave).toHaveBeenCalledTimes(2);
    expect(onSave).toHaveBeenLastCalledWith({ "retired-native": ["free", "plus"] });
  });
});
