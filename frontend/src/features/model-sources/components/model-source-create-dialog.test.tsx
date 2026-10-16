import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/utils";

import { ModelSourceCreateDialog } from "./model-source-create-dialog";

async function fillSource(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Name"), "relay");
  await user.type(screen.getByLabelText("Base URL"), "http://relay.test/v1");
}

describe("ModelSourceCreateDialog", () => {
  it("creates a typed model row with web-search forwarding", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<ModelSourceCreateDialog open busy={false} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    await fillSource(user);
    await user.type(screen.getByLabelText("Model ID 1"), "http/gpt-6-astra");
    await user.type(screen.getByLabelText("Upstream model 1"), "gpt-6-astra");
    await user.click(screen.getByRole("checkbox", { name: "Web search" }));
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const [model] = onSubmit.mock.calls[0][0].models;
    expect(model).toMatchObject({ model: "http/gpt-6-astra", supportsTools: true, isEnabled: true });
    expect(JSON.parse(model.rawMetadataJson)).toEqual({
      experimental_supported_tools: ["web_search"],
      upstream_model: "gpt-6-astra",
    });
  });

  it("shows the default context window only while the field is blank", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ModelSourceCreateDialog open busy={false} onOpenChange={vi.fn()} onSubmit={vi.fn()} />);
    const hint =
      "Blank advertises the default of 128,000 tokens to Codex. Set the model's real window so long threads can compact.";

    expect(screen.getByText(hint)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Context Window"), "272000");
    expect(screen.queryByText(hint)).not.toBeInTheDocument();
  });

  it("replaces the blank starter row with pasted models", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<ModelSourceCreateDialog open busy={false} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    await fillSource(user);
    await user.click(screen.getByRole("button", { name: "Paste list" }));
    await user.type(screen.getByRole("textbox", { name: /One entry per line/ }), "http/a=a\nhttp/b");
    await user.click(screen.getByRole("button", { name: "Add to list" }));
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0].models.map((model: { model: string }) => model.model)).toEqual(["http/a", "http/b"]);
  });

  it("rejects malformed pasted entries without changing the rows", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ModelSourceCreateDialog open busy={false} onOpenChange={vi.fn()} onSubmit={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Paste list" }));
    await user.type(screen.getByRole("textbox", { name: /One entry per line/ }), "alias=a=b");
    await user.click(screen.getByRole("button", { name: "Add to list" }));

    expect(
      screen.getByText("Use unique model IDs or alias=upstream entries with both sides filled."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Model ID 1")).toHaveValue("");
    expect(screen.queryByLabelText("Model ID 2")).not.toBeInTheDocument();
  });
});
