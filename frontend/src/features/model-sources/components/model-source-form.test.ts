import type { TFunction } from "i18next";
import { describe, expect, it } from "vitest";
import {
  bulkModelRows,
  createModelSourceFormSchema,
  initialModelSourceDraft,
  mergeFastModeMetadata,
  mergeReasoningMetadata,
  mergeSubagentMetadata,
  mergeToolTypeMetadata,
  modelInputsFromForm,
  modelsMissingContextWindow,
  newModelRow,
  parseBulkModelEntries,
  parseReasoningEffortsInput,
  sourceToolTypeStates,
} from "./model-source-form";

const t = ((key: string) => key) as unknown as TFunction;
const schema = createModelSourceFormSchema(t);

describe("model-source-form reasoning effort normalization", () => {
  it("trims whitespace and preserves casing for effort values", () => {
    expect(parseReasoningEffortsInput("  Ultra,   xhigh , low  ")).toEqual([
      "Ultra",
      "xhigh",
      "low",
    ]);
  });

  it("preserves casing for declared default reasoning effort", () => {
    const metadata = mergeReasoningMetadata(
      null,
      true,
      ["Ultra", "provider-specific", "xhigh"],
      "  provider-specific  ",
    );
    const parsed = JSON.parse(metadata ?? "{}");

    expect(parsed.supported_reasoning_levels).toEqual(["Ultra", "provider-specific", "xhigh"]);
    expect(parsed.default_reasoning_level).toBe("provider-specific");
  });
});

describe("model-source rows", () => {
  const values = { name: "source", baseUrl: "https://example.test/v1", apiKey: "" };

  it("creates mixed aliases and identity models with reasoning and tool declarations", () => {
    const parsed = schema.parse({
      ...values,
      models: [newModelRow(" cd/gpt-6-astra ", " cd/linxaq "), { ...newModelRow("plain"), isEnabled: false }],
    });
    const models = modelInputsFromForm(parsed, {
      ...initialModelSourceDraft,
      supportsReasoning: true,
      reasoningEfforts: ["high"],
      defaultReasoningEffort: "high",
      toolTypes: { namespace: true, custom: false, web_search: true },
    });
    expect(models.map((model) => [model.model, model.isEnabled])).toEqual([
      ["cd/gpt-6-astra", true],
      ["plain", false],
    ]);
    expect(JSON.parse(models[0].rawMetadataJson!)).toMatchObject({
      upstream_model: "cd/linxaq",
      supports_reasoning: true,
      experimental_supported_tools: ["namespace", "web_search"],
    });
    expect(JSON.parse(models[1].rawMetadataJson!)).not.toHaveProperty("upstream_model");
  });

  it.each([
    [[newModelRow("")], "modelSources.validation.modelIdRequired"],
    [[newModelRow("a"), newModelRow(" a ")], "modelSources.validation.modelIdDuplicate"],
    [[newModelRow("x".repeat(256))], "modelSources.validation.modelIdTooLong"],
    [[newModelRow("a", "y".repeat(256))], "modelSources.validation.modelIdTooLong"],
    [[], "modelSources.validation.modelsRequired"],
  ])("rejects invalid rows %#", (models, message) => {
    const result = schema.safeParse({ ...values, models });
    expect(result.success).toBe(false);
    expect(result.error?.issues.map((issue) => issue.message)).toContain(message);
  });
});

describe("model-source bulk paste", () => {
  it("parses comma and newline separated aliases", () => {
    expect(parseBulkModelEntries("http/a = a,\nplain\n")).toEqual([
      { model: "http/a", upstreamModel: "a" },
      { model: "plain" },
    ]);
  });

  it.each(["=target", "alias=", "alias=a=b", "alias=a, alias=b", " , ", `alias=${"x".repeat(256)}`])(
    "rejects malformed or duplicate entries: %s",
    (text) => {
      expect(parseBulkModelEntries(text)).toBeNull();
    },
  );

  it("skips public IDs that are already listed", () => {
    const entries = parseBulkModelEntries("http/a=a, http/b=b")!;
    expect(bulkModelRows([newModelRow("http/a", "a")], entries)).toEqual([newModelRow("http/b", "b")]);
  });
});

describe("model-source tool type metadata", () => {
  const raw = (metadata: Record<string, unknown> | null) => ({
    rawMetadataJson: metadata === null ? null : JSON.stringify(metadata),
  });

  it("reports a type only when every model forwards it", () => {
    const states = sourceToolTypeStates([
      raw({ experimental_supported_tools: ["namespace", "web_search"], apply_patch_tool_type: "freeform" }),
      raw({ experimental_supported_tools: ["namespace"] }),
    ]);
    expect(states.enabled).toEqual({ namespace: true, custom: false, web_search: false });
    expect(states.locked).toEqual({ namespace: false, custom: false, web_search: false });
  });

  it("locks types granted by advanced metadata on every model", () => {
    const states = sourceToolTypeStates([
      raw({ multi_agent_version: "v2", tool_mode: "code_mode_only", supports_search_tool: true }),
      raw({ multi_agent_version: "v2", tool_mode: "code_mode_only" }),
    ]);
    expect(states.enabled).toEqual({ namespace: true, custom: true, web_search: false });
    expect(states.locked).toEqual({ namespace: true, custom: true, web_search: false });
    expect(sourceToolTypeStates([]).enabled).toEqual({ namespace: false, custom: false, web_search: false });
  });

  it("adds declarations without touching unrelated keys or the search-tool flag", () => {
    const merged = mergeToolTypeMetadata(
      JSON.stringify({ upstream_model: "gpt", supports_search_tool: false, experimental_supported_tools: ["clock"] }),
      { namespace: true, custom: true, web_search: true },
    );
    expect(JSON.parse(merged!)).toEqual({
      upstream_model: "gpt",
      supports_search_tool: false,
      experimental_supported_tools: ["clock", "namespace", "web_search"],
      apply_patch_tool_type: "freeform",
    });
  });

  it("removes only form-owned declarations when turned off", () => {
    const merged = mergeToolTypeMetadata(
      JSON.stringify({
        apply_patch_tool_type: "freeform",
        experimental_supported_tools: ["namespace", "custom", "web_search", "web_search_preview"],
        multi_agent_version: "v2",
        supports_search_tool: true,
      }),
      { namespace: false, custom: false, web_search: false },
    );
    expect(JSON.parse(merged!)).toEqual({ multi_agent_version: "v2", supports_search_tool: true });
  });

  it("returns the stored metadata unchanged when no toggle changed", () => {
    const stored = '{"experimental_supported_tools":[],"x":1}';
    expect(mergeToolTypeMetadata(stored, {})).toBe(stored);
    expect(mergeToolTypeMetadata(null, { namespace: false })).toBeNull();
  });
});

describe("model-source sub-agent policy metadata", () => {
  it("adds and removes the block flag without touching other keys", () => {
    const blocked = mergeSubagentMetadata(JSON.stringify({ upstream_model: "gpt" }), false);
    expect(JSON.parse(blocked!)).toEqual({ upstream_model: "gpt", block_subagents: true });
    expect(JSON.parse(mergeSubagentMetadata(blocked, true)!)).toEqual({ upstream_model: "gpt" });
    expect(mergeSubagentMetadata(JSON.stringify({ block_subagents: true }), true)).toBeNull();
  });

  it("returns stored metadata unchanged when the policy already matches", () => {
    const stored = '{"x":1}';
    expect(mergeSubagentMetadata(stored, true)).toBe(stored);
    expect(mergeSubagentMetadata(null, true)).toBeNull();
  });

  it("writes the flag for rows created with sub-agents off", () => {
    const parsed = schema.parse({
      name: "source",
      baseUrl: "https://example.test/v1",
      apiKey: "",
      models: [{ ...newModelRow("blocked"), subagentsAllowed: false }, newModelRow("open")],
    });
    const [blocked, open] = modelInputsFromForm(parsed, initialModelSourceDraft);
    expect(JSON.parse(blocked.rawMetadataJson!)).toEqual({ block_subagents: true });
    expect(open.rawMetadataJson).toBeNull();
  });
});

describe("model-source Fast mode metadata", () => {
  const fastTier = { id: "priority", name: "Fast", description: "Priority processing" };

  it("adds and removes both tier keys without touching other keys", () => {
    const fast = mergeFastModeMetadata(JSON.stringify({ upstream_model: "gpt" }), true);
    expect(JSON.parse(fast!)).toEqual({
      upstream_model: "gpt",
      service_tiers: [fastTier],
      additional_speed_tiers: ["fast"],
    });
    expect(JSON.parse(mergeFastModeMetadata(fast, false)!)).toEqual({ upstream_model: "gpt" });
    expect(mergeFastModeMetadata(JSON.stringify({ additional_speed_tiers: ["Fast"] }), false)).toBeNull();
  });

  it("keeps other tiers when switching", () => {
    const flex = { id: "flex", name: "Flex", description: "Cheaper" };
    const stored = JSON.stringify({ service_tiers: [flex], additional_speed_tiers: ["slow"] });
    expect(JSON.parse(mergeFastModeMetadata(stored, true)!)).toEqual({
      service_tiers: [flex, fastTier],
      additional_speed_tiers: ["slow", "fast"],
    });

    const custom = { id: "priority", name: "Fast", description: "2x speed, increased usage" };
    const turnedOff = mergeFastModeMetadata(
      JSON.stringify({ service_tiers: [custom, flex], additional_speed_tiers: ["fast"], default_service_tier: "priority" }),
      false,
    );
    expect(JSON.parse(turnedOff!)).toEqual({ service_tiers: [flex] });
  });

  it("returns stored metadata unchanged when the switch already matches", () => {
    const stored = '{"service_tiers":[{"id":"priority","description":"2x speed, increased usage"}],"x":1}';
    expect(mergeFastModeMetadata(stored, true)).toBe(stored);
    expect(mergeFastModeMetadata('{"additional_speed_tiers":["fast"]}', true)).toBe('{"additional_speed_tiers":["fast"]}');
    expect(mergeFastModeMetadata('{"x":1}', false)).toBe('{"x":1}');
    expect(mergeFastModeMetadata(null, false)).toBeNull();
  });

  it("leaves new rows without Fast and writes it for rows switched on", () => {
    const parsed = schema.parse({
      name: "source",
      baseUrl: "https://example.test/v1",
      apiKey: "",
      models: [newModelRow("plain"), { ...newModelRow("fast"), fastMode: true }],
    });
    const [plain, fast] = modelInputsFromForm(parsed, initialModelSourceDraft);
    expect(plain.rawMetadataJson).toBeNull();
    expect(JSON.parse(fast.rawMetadataJson!)).toEqual({ service_tiers: [fastTier], additional_speed_tiers: ["fast"] });
  });
});

describe("modelsMissingContextWindow", () => {
  it("lists only enabled models without a context window", () => {
    expect(
      modelsMissingContextWindow([
        { model: "http/gpt-6-astra", contextWindow: null, isEnabled: true },
        { model: "http/gpt-6-sol", contextWindow: 272000, isEnabled: true },
        { model: "http/old", contextWindow: null, isEnabled: false },
      ]),
    ).toEqual(["http/gpt-6-astra"]);
  });
});
