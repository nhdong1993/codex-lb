import { z } from "zod";
import type { TFunction } from "i18next";

import type {
  ModelSource,
  ModelSourceModel,
  ModelSourceModelInput,
} from "@/features/model-sources/schemas";

const MAX_MODEL_ID_LENGTH = 255;

// Mirrors DEFAULT_SOURCE_CONTEXT_WINDOW in app/modules/model_sources/catalog.py:
// the window the model catalog advertises for a source model without one.
export const DEFAULT_SOURCE_CONTEXT_WINDOW = 128_000;

// Enabled models that fall back to DEFAULT_SOURCE_CONTEXT_WINDOW in the catalog.
export function modelsMissingContextWindow(
  models: Pick<ModelSourceModel, "model" | "contextWindow" | "isEnabled">[],
): string[] {
  return models.filter((model) => model.isEnabled && model.contextWindow === null).map((model) => model.model);
}

// One editable model row. ``originModel`` is the stored model the row was
// loaded from, so renaming the public ID keeps that model's settings; rows
// added in the form have no origin. ``subagentsAllowed`` mirrors the absence of
// the proxy's ``block_subagents`` metadata flag.
export type ModelRow = {
  model: string;
  upstreamModel: string;
  isEnabled: boolean;
  subagentsAllowed: boolean;
  originModel: string | null;
};

export function createModelSourceFormSchema(t: TFunction) {
  return z.object({
    name: z.string().min(1, t("modelSources.validation.nameRequired")),
    baseUrl: z.string().min(1, t("modelSources.validation.baseUrlRequired")),
    apiKey: z.string(),
    models: z
      .array(
        z.object({
          model: z.string(),
          upstreamModel: z.string(),
          isEnabled: z.boolean(),
          subagentsAllowed: z.boolean(),
          originModel: z.string().nullable(),
        }),
      )
      .min(1, t("modelSources.validation.modelsRequired"))
      .superRefine((rows, ctx) => {
        const seen = new Set<string>();
        rows.forEach((row, index) => {
          const model = row.model.trim();
          const modelError = !model
            ? t("modelSources.validation.modelIdRequired")
            : model.length > MAX_MODEL_ID_LENGTH
              ? t("modelSources.validation.modelIdTooLong")
              : seen.has(model)
                ? t("modelSources.validation.modelIdDuplicate")
                : null;
          seen.add(model);
          if (modelError) {
            ctx.addIssue({ code: "custom", path: [index, "model"], message: modelError });
          }
          if (row.upstreamModel.trim().length > MAX_MODEL_ID_LENGTH) {
            ctx.addIssue({
              code: "custom",
              path: [index, "upstreamModel"],
              message: t("modelSources.validation.modelIdTooLong"),
            });
          }
        });
      }),
  });
}

export type ModelSourceFormValues = z.infer<ReturnType<typeof createModelSourceFormSchema>>;

export type ModelEntry = { model: string; upstreamModel?: string };

export function newModelRow(model = "", upstreamModel = ""): ModelRow {
  return { model, upstreamModel, isEnabled: true, subagentsAllowed: true, originModel: null };
}

// Bulk paste keeps the original text syntax: ``model`` or ``alias=upstream``
// entries separated by commas or newlines. Returns null when any entry is
// malformed or a public ID repeats, so the operator can fix the text.
export function parseBulkModelEntries(value: string): ModelEntry[] | null {
  const parts = value.split(/[\n,]/).map((entry) => entry.trim()).filter(Boolean);
  if (!parts.length) return null;
  const entries: ModelEntry[] = [];
  for (const part of parts) {
    const sides = part.split("=").map((side) => side.trim());
    if (sides.length > 2) return null;
    const [model, upstreamModel] = sides;
    if (!model || model.length > MAX_MODEL_ID_LENGTH) return null;
    if (upstreamModel !== undefined && (!upstreamModel || upstreamModel.length > MAX_MODEL_ID_LENGTH)) {
      return null;
    }
    entries.push({ model, ...(upstreamModel !== undefined ? { upstreamModel } : {}) });
  }
  return new Set(entries.map((entry) => entry.model)).size === entries.length ? entries : null;
}

// Rows for pasted entries whose public ID is not already listed.
export function bulkModelRows(existing: ModelRow[], entries: ModelEntry[]): ModelRow[] {
  const present = new Set(existing.map((row) => row.model.trim()));
  return entries
    .filter((entry) => !present.has(entry.model))
    .map((entry) => newModelRow(entry.model, entry.upstreamModel ?? ""));
}

export function modelRowsFromSource(source: ModelSource): ModelRow[] {
  return source.models.map((model) => {
    const metadata = parseMetadata(model.rawMetadataJson);
    const upstream = metadata.upstream_model;
    return {
      model: model.model,
      upstreamModel: typeof upstream === "string" ? upstream.trim() : "",
      isEnabled: model.isEnabled,
      subagentsAllowed: metadata.block_subagents !== true,
      originModel: model.model,
    };
  });
}

function parseMetadata(rawMetadataJson: string | null | undefined): Record<string, unknown> {
  if (!rawMetadataJson) return {};
  try {
    const parsed: unknown = JSON.parse(rawMetadataJson);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? { ...(parsed as Record<string, unknown>) }
      : {};
  } catch {
    return {};
  }
}

function serializeMetadata(metadata: Record<string, unknown>): string | null {
  return Object.keys(metadata).length > 0 ? JSON.stringify(metadata) : null;
}

// The proxy refuses Codex sub-agent (spawn_agent) traffic for models carrying
// ``"block_subagents": true`` while still forwarding MCP tools.
export function mergeSubagentMetadata(existing: string | null | undefined, subagentsAllowed: boolean): string | null {
  const metadata = parseMetadata(existing);
  if (subagentsAllowed === (metadata.block_subagents !== true)) return existing ?? null;
  if (subagentsAllowed) delete metadata.block_subagents;
  else metadata.block_subagents = true;
  return serializeMetadata(metadata);
}

export function mergeUpstreamModelMetadata(
  existing: string | null | undefined,
  upstreamModel?: string,
): string | null {
  const metadata = parseMetadata(existing);
  if (upstreamModel) metadata.upstream_model = upstreamModel;
  else delete metadata.upstream_model;
  return serializeMetadata(metadata);
}

// Non-function Responses tool types the proxy forwards to a source only when
// the source model declares them (see source_model_supported_tool_types).
// Function tools are always forwarded.
export const SOURCE_TOOL_TYPES = ["namespace", "custom", "web_search"] as const;
export type SourceToolType = (typeof SOURCE_TOOL_TYPES)[number];
export type SourceToolTypeFlags = Record<SourceToolType, boolean>;

const NO_SOURCE_TOOL_TYPES: SourceToolTypeFlags = { namespace: false, custom: false, web_search: false };
const WEB_SEARCH_TOOL_TYPES = ["web_search", "web_search_preview"];

function experimentalTools(metadata: Record<string, unknown>): string[] {
  const value = metadata.experimental_supported_tools;
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

// Declarations the form owns: ``experimental_supported_tools`` entries and
// ``apply_patch_tool_type``.
function declaresToolType(metadata: Record<string, unknown>, type: SourceToolType): boolean {
  const declared = experimentalTools(metadata);
  if (type === "namespace") return declared.includes("namespace");
  if (type === "custom") return metadata.apply_patch_tool_type === "freeform" || declared.includes("custom");
  return declared.some((item) => WEB_SEARCH_TOOL_TYPES.includes(item));
}

// Advanced keys that also change Codex's own behavior; the form shows their
// grant but never edits them. ``supports_search_tool`` means "use tool_search"
// to Codex, which hides MCP tools behind a type sources do not receive.
function grantsToolTypeByAdvancedKey(metadata: Record<string, unknown>, type: SourceToolType): boolean {
  if (type === "namespace") {
    return typeof metadata.multi_agent_version === "string" && metadata.multi_agent_version.trim() !== "";
  }
  if (type === "custom") return metadata.tool_mode === "code_mode_only";
  return metadata.supports_search_tool === true;
}

export type SourceToolTypeStates = { enabled: SourceToolTypeFlags; locked: SourceToolTypeFlags };

// A type counts as forwarded for the source only when every model forwards it.
export function sourceToolTypeStates(models: Pick<ModelSourceModel, "rawMetadataJson">[]): SourceToolTypeStates {
  const metadata = models.map((model) => parseMetadata(model.rawMetadataJson));
  const every = (predicate: (item: Record<string, unknown>) => boolean) =>
    metadata.length > 0 && metadata.every(predicate);
  const enabled = { ...NO_SOURCE_TOOL_TYPES };
  const locked = { ...NO_SOURCE_TOOL_TYPES };
  for (const type of SOURCE_TOOL_TYPES) {
    locked[type] = every((item) => grantsToolTypeByAdvancedKey(item, type));
    enabled[type] = every((item) => declaresToolType(item, type) || grantsToolTypeByAdvancedKey(item, type));
  }
  return { enabled, locked };
}

export function mergeToolTypeMetadata(
  existing: string | null | undefined,
  changes: Partial<SourceToolTypeFlags>,
): string | null {
  if (Object.keys(changes).length === 0) return existing ?? null;
  const metadata = parseMetadata(existing);
  let declared = experimentalTools(metadata);
  const hadDeclaredList = Array.isArray(metadata.experimental_supported_tools);
  const add = (item: string) => {
    if (!declared.includes(item)) declared = [...declared, item];
  };
  const remove = (items: string[]) => {
    declared = declared.filter((item) => !items.includes(item));
  };
  if (changes.namespace !== undefined) {
    if (changes.namespace) add("namespace");
    else remove(["namespace"]);
  }
  if (changes.custom !== undefined) {
    if (changes.custom) {
      metadata.apply_patch_tool_type = "freeform";
    } else {
      if (metadata.apply_patch_tool_type === "freeform") delete metadata.apply_patch_tool_type;
      remove(["custom"]);
    }
  }
  if (changes.web_search !== undefined) {
    if (changes.web_search) add("web_search");
    else remove(WEB_SEARCH_TOOL_TYPES);
  }
  if (declared.length > 0) metadata.experimental_supported_tools = declared;
  else if (hadDeclaredList) delete metadata.experimental_supported_tools;
  return serializeMetadata(metadata);
}

// Per-model settings the dialogs apply uniformly across every model of the
// source. Pricing is USD per 1M tokens; blank means "unknown" (cost settles
// at $0 for that model).
export type ModelSourceDraft = {
  supportsChatCompletions: boolean;
  supportsResponses: boolean;
  supportsResponsesWebsocket: boolean;
  supportsAudioTranscriptions: boolean;
  supportsEmbeddings: boolean;
  supportsStreaming: boolean;
  supportsTools: boolean;
  supportsVision: boolean;
  supportsReasoning: boolean;
  reasoningEffortsInput: string;
  reasoningEfforts: string[];
  defaultReasoningEffort: string;
  toolTypes: SourceToolTypeFlags;
  contextWindow: string;
  maxOutputTokens: string;
  inputPer1M: string;
  cachedInputPer1M: string;
  outputPer1M: string;
  audioPerMinute: string;
};

export const initialModelSourceDraft: ModelSourceDraft = {
  supportsChatCompletions: true,
  supportsResponses: false,
  supportsResponsesWebsocket: false,
  supportsAudioTranscriptions: false,
  supportsEmbeddings: false,
  supportsStreaming: true,
  supportsTools: false,
  supportsVision: false,
  supportsReasoning: false,
  reasoningEffortsInput: "",
  reasoningEfforts: [],
  defaultReasoningEffort: "",
  toolTypes: NO_SOURCE_TOOL_TYPES,
  contextWindow: "",
  maxOutputTokens: "",
  inputPer1M: "",
  cachedInputPer1M: "",
  outputPer1M: "",
  audioPerMinute: "",
};

export function modelSourceDraftReducer(
  state: ModelSourceDraft,
  patch: Partial<ModelSourceDraft>,
): ModelSourceDraft {
  return { ...state, ...patch };
}

export function parsePositiveInt(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function parseNonNegativeFloat(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number.parseFloat(trimmed);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : null;
}

// The backend has no first-class reasoning column; the flag lives in the
// model's raw metadata JSON, which the proxy reads to pass reasoning fields
// through and to advertise supports_reasoning in /v1/models. Merge it into
// any raw metadata the model already carries so other keys survive edits.
const DEFAULT_REASONING_EFFORTS = ["low", "medium", "high"];

function normalizeReasoningEffort(value: string): string {
  return value.trim();
}

function dedupeReasoningEfforts(values: Iterable<string>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const normalized = normalizeReasoningEffort(value);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    result.push(normalized);
  }
  return result;
}

export function parseReasoningEffortsInput(value: string): string[] {
  return dedupeReasoningEfforts(value.split(/[\n,]/));
}

function normalizeDefaultReasoningEffort(
  reasoningEfforts: string[],
  defaultReasoningEffort: string,
): string {
  const normalizedDefault = normalizeReasoningEffort(defaultReasoningEffort);
  if (normalizedDefault && reasoningEfforts.includes(normalizedDefault)) {
    return normalizedDefault;
  }
  return reasoningEfforts[0] ?? "";
}

export function mergeReasoningMetadata(
  existing: string | null | undefined,
  supportsReasoning: boolean,
  reasoningEfforts: string[] = [],
  defaultReasoningEffort = "",
): string | null {
  const metadata = parseMetadata(existing);
  if (supportsReasoning) {
    metadata.supports_reasoning = true;
    if (reasoningEfforts.length > 0) {
      metadata.supported_reasoning_levels = reasoningEfforts;
      metadata.default_reasoning_level = normalizeDefaultReasoningEffort(
        reasoningEfforts,
        defaultReasoningEffort,
      );
    } else {
      delete metadata.supported_reasoning_levels;
      delete metadata.default_reasoning_level;
    }
  } else {
    delete metadata.supports_reasoning;
    delete metadata.supported_reasoning_levels;
    delete metadata.default_reasoning_level;
  }
  return serializeMetadata(metadata);
}

export function modelInputsFromForm(
  values: ModelSourceFormValues,
  draft: ModelSourceDraft,
): ModelSourceModelInput[] {
  const contextWindow = parsePositiveInt(draft.contextWindow);
  const maxOutputTokens = parsePositiveInt(draft.maxOutputTokens);
  const inputPer1M = parseNonNegativeFloat(draft.inputPer1M);
  const cachedInputPer1M = parseNonNegativeFloat(draft.cachedInputPer1M);
  const outputPer1M = parseNonNegativeFloat(draft.outputPer1M);
  const audioPerMinute = parseNonNegativeFloat(draft.audioPerMinute);
  return values.models.map((row) => {
    const model = row.model.trim();
    return {
      model,
      displayName: model,
      contextWindow,
      maxOutputTokens,
      supportsStreaming: draft.supportsStreaming,
      supportsTools: draft.supportsTools,
      supportsVision: draft.supportsVision,
      inputPer1M,
      cachedInputPer1M,
      outputPer1M,
      audioPerMinute,
      rawMetadataJson: mergeUpstreamModelMetadata(
        mergeSubagentMetadata(
          mergeToolTypeMetadata(
            mergeReasoningMetadata(null, draft.supportsReasoning, draft.reasoningEfforts, draft.defaultReasoningEffort),
            draft.toolTypes,
          ),
          row.subagentsAllowed,
        ),
        row.upstreamModel.trim() || undefined,
      ),
      isEnabled: row.isEnabled,
    };
  });
}

function numberToInput(value: number | null | undefined): string {
  return value === null || value === undefined ? "" : String(value);
}

// Derive the shared draft from an existing source. The create UI applies one
// set of per-model settings to every model, so editing mirrors that by reading
// the first model's values as the representative settings.
function parseReasoningMetadata(rawMetadataJson: string | null | undefined): {
  supportsReasoning: boolean;
  reasoningEffortsInput: string;
  reasoningEfforts: string[];
  defaultReasoningEffort: string;
} {
  const metadata = parseMetadata(rawMetadataJson);
  const supportsReasoning = metadata.supports_reasoning === true;
  const declaredLevels = Array.isArray(metadata.supported_reasoning_levels)
    ? dedupeReasoningEfforts(
        metadata.supported_reasoning_levels.flatMap((value): string[] => {
          if (typeof value === "string") return [value];
          if (typeof value !== "object" || value === null || Array.isArray(value)) return [];
          const effort = (value as Record<string, unknown>).effort;
          return typeof effort === "string" ? [effort] : [];
        }),
      )
    : [];
  const reasoningEfforts =
    supportsReasoning && declaredLevels.length === 0 ? DEFAULT_REASONING_EFFORTS : declaredLevels;

  return {
    supportsReasoning,
    reasoningEffortsInput: reasoningEfforts.join(", "),
    reasoningEfforts,
    defaultReasoningEffort: normalizeDefaultReasoningEffort(
      reasoningEfforts,
      typeof metadata.default_reasoning_level === "string" ? metadata.default_reasoning_level : "",
    ),
  };
}

export function draftFromSource(source: ModelSource): ModelSourceDraft {
  const firstModel = source.models[0];
  const reasoningMetadata = parseReasoningMetadata(firstModel?.rawMetadataJson);
  return {
    supportsChatCompletions: source.supportsChatCompletions,
    supportsResponses: source.supportsResponses,
    supportsResponsesWebsocket: source.supportsResponsesWebsocket,
    supportsAudioTranscriptions: source.supportsAudioTranscriptions,
    supportsEmbeddings: source.supportsEmbeddings,
    supportsStreaming: firstModel?.supportsStreaming ?? true,
    supportsTools: firstModel?.supportsTools ?? false,
    supportsVision: firstModel?.supportsVision ?? false,
    supportsReasoning: reasoningMetadata.supportsReasoning,
    reasoningEffortsInput: reasoningMetadata.reasoningEffortsInput,
    reasoningEfforts: reasoningMetadata.reasoningEfforts,
    defaultReasoningEffort: reasoningMetadata.defaultReasoningEffort,
    toolTypes: sourceToolTypeStates(source.models).enabled,
    contextWindow: numberToInput(firstModel?.contextWindow),
    maxOutputTokens: numberToInput(firstModel?.maxOutputTokens),
    inputPer1M: numberToInput(firstModel?.inputPer1M),
    cachedInputPer1M: numberToInput(firstModel?.cachedInputPer1M),
    outputPer1M: numberToInput(firstModel?.outputPer1M),
    audioPerMinute: numberToInput(firstModel?.audioPerMinute),
  };
}
