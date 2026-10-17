import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/utils";
import type { ModelSource } from "@/features/model-sources/schemas";

import { ModelSourceEditDialog } from "./model-source-edit-dialog";

function createModelSource(overrides: Partial<ModelSource> = {}): ModelSource {
  return {
    id: "src_1",
    name: "vllm-local",
    kind: "openai_compatible",
    baseUrl: "http://127.0.0.1:8000/v1",
    isEnabled: true,
    healthStatus: "unknown",
    supportsChatCompletions: true,
    supportsResponses: false,
    supportsResponsesWebsocket: false,
    supportsAudioTranscriptions: false,
    supportsEmbeddings: false,
    timeoutSeconds: null,
    maxConcurrency: null,
    createdAt: "2026-07-03T00:00:00Z",
    updatedAt: "2026-07-03T00:00:00Z",
    models: [
      {
        id: 1,
        sourceId: "src_1",
        model: "Qwen/Qwen3.6-27B-FP8",
        displayName: "Qwen/Qwen3.6-27B-FP8",
        contextWindow: 32768,
        maxOutputTokens: 4096,
        supportsStreaming: true,
        supportsTools: true,
        supportsVision: false,
        inputPer1M: 0.5,
        cachedInputPer1M: null,
        outputPer1M: 1.5,
        audioPerMinute: null,
        rawMetadataJson: null,
        isEnabled: true,
        createdAt: "2026-07-03T00:00:00Z",
        updatedAt: "2026-07-03T00:00:00Z",
      },
    ],
    ...overrides,
  };
}

describe("ModelSourceEditDialog", () => {
  it("prefills existing fields including pricing and models", () => {
    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={createModelSource()}
        onOpenChange={vi.fn()}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByLabelText("Name")).toHaveValue("vllm-local");
    expect(screen.getByLabelText("Base URL")).toHaveValue("http://127.0.0.1:8000/v1");
    expect(screen.getByDisplayValue("Qwen/Qwen3.6-27B-FP8")).toBeInTheDocument();
    expect(screen.getByDisplayValue("0.5")).toBeInTheDocument();
    expect(screen.getByDisplayValue("1.5")).toBeInTheDocument();
  });

  it("submits edited pricing and omits blank api key", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={createModelSource()}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const outputPrice = screen.getByDisplayValue("1.5");
    await user.clear(outputPrice);
    await user.type(outputPrice, "2.25");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    const [sourceId, payload] = onSubmit.mock.calls[0];
    expect(sourceId).toBe("src_1");
    expect("apiKey" in payload).toBe(false);
    expect(payload.models).toHaveLength(1);
    expect(payload.models[0]).toMatchObject({
      model: "Qwen/Qwen3.6-27B-FP8",
      inputPer1M: 0.5,
      outputPer1M: 2.25,
    });
    expect(payload.supportsAudioTranscriptions).toBe(false);
    expect(payload.supportsEmbeddings).toBe(false);
  });

  it("carries an enabled embeddings capability through submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={createModelSource({ supportsEmbeddings: true })}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    const [, payload] = onSubmit.mock.calls[0];
    expect(payload.supportsEmbeddings).toBe(true);
  });

  it("preserves disabled model rows during edits", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource({
      models: [
        {
          ...createModelSource().models[0],
          model: "enabled-model",
          displayName: "enabled-model",
          isEnabled: true,
          contextWindow: 2048,
          supportsVision: true,
        },
        {
          ...createModelSource().models[0],
          id: 2,
          model: "disabled-model",
          displayName: "disabled-model",
          isEnabled: false,
          contextWindow: 4096,
          supportsVision: false,
        },
      ],
    });

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={source}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const outputPrice = screen.getByDisplayValue("1.5");
    await user.clear(outputPrice);
    await user.type(outputPrice, "2.0");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    expect(onSubmit.mock.calls[0][1].models).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          model: "enabled-model",
          isEnabled: true,
          contextWindow: 2048,
          outputPer1M: 2,
          supportsVision: true,
        }),
        expect.objectContaining({
          model: "disabled-model",
          isEnabled: false,
          contextWindow: 4096,
          outputPer1M: 2,
          supportsVision: false,
        }),
      ]),
    );
  });

  it("omits model rows when only source-level fields changed", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource({
      models: [
        {
          ...createModelSource().models[0],
          model: "m-one",
          displayName: "m-one",
          contextWindow: 2048,
          outputPer1M: 1.0,
        },
        {
          ...createModelSource().models[0],
          id: 2,
          model: "m-two",
          displayName: "m-two",
          contextWindow: 4096,
          outputPer1M: 2.0,
        },
      ],
    });

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={source}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "vllm-local-updated");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    const payload = onSubmit.mock.calls[0][1];
    expect(payload.name).toBe("vllm-local-updated");
    expect(payload.models).toBeUndefined();
  });

  it("prefills and submits the audio per-minute rate", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    source.models[0].audioPerMinute = 0.3;

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={source}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const audioPrice = screen.getByDisplayValue("0.3");
    await user.clear(audioPrice);
    await user.type(audioPrice, "0.45");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    expect(onSubmit.mock.calls[0][1].models[0].audioPerMinute).toBe(0.45);
  });

  it("toggles reasoning support via raw metadata while keeping other keys", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    source.models[0].rawMetadataJson = '{"custom_key": "kept"}';

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={source}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    expect(screen.getByRole("checkbox", { name: "Reasoning" })).not.toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: "Reasoning" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    const rawMetadata = JSON.parse(onSubmit.mock.calls[0][1].models[0].rawMetadataJson);
    expect(rawMetadata).toEqual({
      custom_key: "kept",
      supports_reasoning: true,
      supported_reasoning_levels: ["low", "medium", "high"],
      default_reasoning_level: "medium",
    });
  });

  it("prefills the reasoning toggle from raw metadata", () => {
    const source = createModelSource();
    source.models[0].rawMetadataJson = JSON.stringify({
      supports_reasoning: true,
      supported_reasoning_levels: [
        { effort: "none", description: "disable chain of thought" },
        "provider-specific",
        "ultra",
      ],
      default_reasoning_level: "provider-specific",
    });

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={source}
        onOpenChange={vi.fn()}
        onSubmit={vi.fn().mockResolvedValue(undefined)}
      />,
    );

    expect(screen.getByRole("checkbox", { name: "Reasoning" })).toBeChecked();
    expect(screen.getByLabelText("Supported reasoning efforts")).toHaveValue(
      "none, provider-specific, ultra",
    );
    expect(screen.getByRole("combobox", { name: "Default reasoning effort" })).toHaveTextContent(
      "provider-specific",
    );
  });

  it("keeps arbitrary reasoning efforts and renormalizes a stale default", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    source.models[0].rawMetadataJson = JSON.stringify({
      supports_reasoning: true,
      supported_reasoning_levels: ["none", "provider-specific", "ultra"],
      default_reasoning_level: "provider-specific",
    });

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={source}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    const reasoningEfforts = screen.getByLabelText("Supported reasoning efforts");
    await user.clear(reasoningEfforts);
    await user.type(reasoningEfforts, "none, custom-tier");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    const rawMetadata = JSON.parse(onSubmit.mock.calls[0][1].models[0].rawMetadataJson);
    expect(rawMetadata).toEqual({
      supports_reasoning: true,
      supported_reasoning_levels: ["none", "custom-tier"],
      default_reasoning_level: "none",
    });
  });

  it("sends the api key only when the field is filled", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ModelSourceEditDialog
        open
        busy={false}
        source={createModelSource()}
        onOpenChange={vi.fn()}
        onSubmit={onSubmit}
      />,
    );

    await user.type(screen.getByLabelText("Upstream API key"), "sk-new-token");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    expect(onSubmit.mock.calls[0][1].apiKey).toBe("sk-new-token");
  });
});

async function submitAndGetPayload(onSubmit: ReturnType<typeof vi.fn>, user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Save" }));
  await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
  return onSubmit.mock.calls[0][1];
}

describe("ModelSourceEditDialog model rows", () => {
  it("renames a row into an alias without losing capabilities or disabled state", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    source.models[0].rawMetadataJson = JSON.stringify({ multi_agent_version: "v2", base_instructions: "Spawn agents" });
    source.models[0].isEnabled = false;
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    await user.clear(screen.getByLabelText("Model ID 1"));
    await user.type(screen.getByLabelText("Model ID 1"), "cd/gpt-6-astra");
    await user.type(screen.getByLabelText("Upstream model 1"), source.models[0].model);
    const model = (await submitAndGetPayload(onSubmit, user)).models[0];
    expect(model).toMatchObject({ model: "cd/gpt-6-astra", displayName: "cd/gpt-6-astra", contextWindow: 32768,
      supportsTools: true, inputPer1M: 0.5, outputPer1M: 1.5, isEnabled: false });
    expect(JSON.parse(model.rawMetadataJson)).toEqual({ multi_agent_version: "v2", base_instructions: "Spawn agents", upstream_model: source.models[0].model });
  });

  it.each([false, true])("preserves an alias through pricing edits or explicitly removes it: %s", async (removeAlias) => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    source.models[0].rawMetadataJson = JSON.stringify({ upstream_model: "cd/linxaq", multi_agent_version: "v2" });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    expect(screen.getByLabelText("Upstream model 1")).toHaveValue("cd/linxaq");
    if (removeAlias) {
      await user.clear(screen.getByLabelText("Upstream model 1"));
    } else {
      const price = screen.getByDisplayValue("1.5");
      await user.clear(price);
      await user.type(price, "2");
    }
    const metadata = JSON.parse((await submitAndGetPayload(onSubmit, user)).models[0].rawMetadataJson);
    expect(metadata.multi_agent_version).toBe("v2");
    expect(metadata.upstream_model).toBe(removeAlias ? undefined : "cd/linxaq");
  });

  it("disables a single model without changing the others", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const base = createModelSource().models[0];
    const source = createModelSource({
      models: [
        { ...base, model: "m-one", displayName: "m-one" },
        { ...base, id: 2, model: "m-two", displayName: "m-two", isEnabled: false },
        { ...base, id: 3, model: "m-three", displayName: "m-three" },
      ],
    });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("switch", { name: "Enable m-one" }));
    const models = (await submitAndGetPayload(onSubmit, user)).models;
    expect(models.map((model: { model: string; isEnabled: boolean }) => [model.model, model.isEnabled])).toEqual([
      ["m-one", false],
      ["m-two", false],
      ["m-three", true],
    ]);
  });

  it("bulk-pastes new rows that take the current source settings and skips listed IDs", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    source.models[0].rawMetadataJson = JSON.stringify({
      supports_reasoning: true,
      supported_reasoning_levels: ["low", "high"],
      default_reasoning_level: "high",
      experimental_supported_tools: ["namespace"],
    });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Paste list" }));
    await user.type(screen.getByRole("textbox", { name: /One entry per line/ }), `${source.models[0].model}, http/new=upstream-new`);
    await user.click(screen.getByRole("button", { name: "Add to list" }));
    expect(screen.getByLabelText("Model ID 2")).toHaveValue("http/new");
    expect(screen.queryByLabelText("Model ID 3")).not.toBeInTheDocument();

    const models = (await submitAndGetPayload(onSubmit, user)).models;
    expect(models).toHaveLength(2);
    expect(models[1]).toMatchObject({ model: "http/new", contextWindow: 32768, inputPer1M: 0.5, outputPer1M: 1.5,
      supportsTools: true, isEnabled: true });
    expect(JSON.parse(models[1].rawMetadataJson)).toEqual({
      supports_reasoning: true,
      supported_reasoning_levels: ["low", "high"],
      default_reasoning_level: "high",
      experimental_supported_tools: ["namespace"],
      upstream_model: "upstream-new",
    });
  });

  it("keeps an active filter reachable after deleting its only match", async () => {
    const user = userEvent.setup();
    const base = createModelSource().models[0];
    const source = createModelSource({
      models: Array.from({ length: 6 }, (_, index) => ({
        ...base,
        id: index + 1,
        model: `m-${index + 1}`,
        displayName: `m-${index + 1}`,
      })),
    });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={vi.fn()} />);
    await user.type(screen.getByRole("textbox", { name: "Filter models" }), "m-6");
    await user.click(screen.getByRole("button", { name: "Remove m-6" }));
    expect(screen.getByText("No models match the filter.")).toBeInTheDocument();

    await user.clear(screen.getByRole("textbox", { name: "Filter models" }));
    expect(screen.getAllByRole("textbox", { name: /^Model ID \d$/ })).toHaveLength(5);
    expect(screen.queryByRole("textbox", { name: "Filter models" })).not.toBeInTheDocument();
  });

  it("blocks submit on duplicate model IDs", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={createModelSource()} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    await user.click(screen.getByRole("button", { name: "Add model" }));
    await user.type(screen.getByLabelText("Model ID 2"), "Qwen/Qwen3.6-27B-FP8");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("This model ID is already listed")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("ModelSourceEditDialog tool forwarding", () => {
  it("declares MCP forwarding on every model while keeping other metadata", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const base = createModelSource().models[0];
    const source = createModelSource({
      models: [
        { ...base, model: "http/a", supportsTools: false, rawMetadataJson: JSON.stringify({ upstream_model: "a", supports_search_tool: false }) },
        { ...base, id: 2, model: "http/b", supportsTools: false, rawMetadataJson: JSON.stringify({ experimental_supported_tools: ["web_search"] }) },
      ],
    });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    const mcp = screen.getByRole("checkbox", { name: "MCP & sub-agents" });
    expect(mcp).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Web search" })).not.toBeChecked();
    await user.click(mcp);
    expect(screen.getByRole("checkbox", { name: "Advertise tool support" })).toBeChecked();

    const models = (await submitAndGetPayload(onSubmit, user)).models;
    expect(models.map((model: { supportsTools: boolean }) => model.supportsTools)).toEqual([true, true]);
    expect(JSON.parse(models[0].rawMetadataJson)).toEqual({
      upstream_model: "a",
      supports_search_tool: false,
      experimental_supported_tools: ["namespace"],
    });
    expect(JSON.parse(models[1].rawMetadataJson)).toEqual({ experimental_supported_tools: ["web_search", "namespace"] });
  });

  it("locks types granted by advanced metadata and leaves them untouched", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    const stored = { tool_mode: "code_mode_only", multi_agent_version: "v2", supports_search_tool: true };
    source.models[0].rawMetadataJson = JSON.stringify(stored);
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    for (const name of ["MCP & sub-agents", "apply_patch (file edits)", "Web search"]) {
      const checkbox = screen.getByRole("checkbox", { name });
      expect(checkbox).toBeChecked();
      expect(checkbox).toBeDisabled();
    }
    const price = screen.getByDisplayValue("1.5");
    await user.clear(price);
    await user.type(price, "2");
    expect(JSON.parse((await submitAndGetPayload(onSubmit, user)).models[0].rawMetadataJson)).toEqual(stored);
  });
});

describe("ModelSourceEditDialog sub-agent switch", () => {
  it("blocks sub-agents on one model and leaves the others unchanged", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const base = createModelSource().models[0];
    const otherMetadata = JSON.stringify({ upstream_model: "two", multi_agent_version: "v2" });
    const source = createModelSource({
      models: [
        { ...base, model: "m-one", displayName: "m-one", rawMetadataJson: JSON.stringify({ upstream_model: "one" }) },
        { ...base, id: 2, model: "m-two", displayName: "m-two", rawMetadataJson: otherMetadata },
      ],
    });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    const subagents = screen.getByRole("switch", { name: "Allow sub-agents on m-one" });
    expect(subagents).toBeChecked();
    await user.click(subagents);

    const models = (await submitAndGetPayload(onSubmit, user)).models;
    expect(JSON.parse(models[0].rawMetadataJson)).toEqual({ upstream_model: "one", block_subagents: true });
    expect(models[1].rawMetadataJson).toBe(otherMetadata);
  });

  it("re-allows sub-agents by removing the flag", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const source = createModelSource();
    source.models[0].rawMetadataJson = JSON.stringify({ block_subagents: true, supports_reasoning: true });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    const subagents = screen.getByRole("switch", { name: `Allow sub-agents on ${source.models[0].model}` });
    expect(subagents).not.toBeChecked();
    await user.click(subagents);

    const [model] = (await submitAndGetPayload(onSubmit, user)).models;
    expect(JSON.parse(model.rawMetadataJson)).toEqual({ supports_reasoning: true });
  });
});

describe("ModelSourceEditDialog Fast switch", () => {
  it("turns on Fast for one model and leaves the others unchanged", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const base = createModelSource().models[0];
    const otherMetadata = JSON.stringify({ upstream_model: "two", block_subagents: true });
    const source = createModelSource({
      models: [
        { ...base, model: "m-one", displayName: "m-one", rawMetadataJson: JSON.stringify({ upstream_model: "one" }) },
        { ...base, id: 2, model: "m-two", displayName: "m-two", rawMetadataJson: otherMetadata },
      ],
    });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    const fast = screen.getByRole("switch", { name: "Offer Fast mode on m-one" });
    expect(fast).not.toBeChecked();
    await user.click(fast);

    const models = (await submitAndGetPayload(onSubmit, user)).models;
    expect(JSON.parse(models[0].rawMetadataJson)).toEqual({
      upstream_model: "one",
      service_tiers: [{ id: "priority", name: "Fast", description: "Priority processing" }],
      additional_speed_tiers: ["fast"],
    });
    expect(models[1].rawMetadataJson).toBe(otherMetadata);
  });

  it("turns off Fast and keeps other service tiers", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const flex = { id: "flex", name: "Flex", description: "Cheaper" };
    const source = createModelSource();
    source.models[0].rawMetadataJson = JSON.stringify({
      service_tiers: [{ id: "priority", name: "Fast", description: "2x speed, increased usage" }, flex],
      additional_speed_tiers: ["fast"],
      supports_reasoning: true,
    });
    renderWithProviders(<ModelSourceEditDialog open busy={false} source={source} onOpenChange={vi.fn()} onSubmit={onSubmit} />);
    const fast = screen.getByRole("switch", { name: `Offer Fast mode on ${source.models[0].model}` });
    expect(fast).toBeChecked();
    await user.click(fast);

    const [model] = (await submitAndGetPayload(onSubmit, user)).models;
    expect(JSON.parse(model.rawMetadataJson)).toEqual({ service_tiers: [flex], supports_reasoning: true });
  });
});
