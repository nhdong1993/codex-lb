import { useReducer } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Form } from "@/components/ui/form";
import { ModelSourceFormFields } from "@/features/model-sources/components/model-source-form-fields";
import {
  SOURCE_TOOL_TYPES,
  createModelSourceFormSchema,
  draftFromSource,
  mergeReasoningMetadata,
  mergeSubagentMetadata,
  mergeToolTypeMetadata,
  mergeUpstreamModelMetadata,
  modelRowsFromSource,
  modelSourceDraftReducer,
  parseNonNegativeFloat,
  parsePositiveInt,
  sourceToolTypeStates,
  type ModelRow,
  type ModelSourceDraft,
  type ModelSourceFormValues,
  type SourceToolTypeFlags,
} from "@/features/model-sources/components/model-source-form";
import type {
  ModelSource,
  ModelSourceModel,
  ModelSourceUpdateRequest,
  ModelSourceModelInput,
} from "@/features/model-sources/schemas";

type ModelDraftChangeFlags = {
  contextWindow: boolean;
  maxOutputTokens: boolean;
  inputPer1M: boolean;
  cachedInputPer1M: boolean;
  outputPer1M: boolean;
  audioPerMinute: boolean;
  supportsStreaming: boolean;
  supportsTools: boolean;
  supportsVision: boolean;
  supportsReasoning: boolean;
  toolTypes: Partial<SourceToolTypeFlags>;
};

function getModelDraftChangeFlags(
  draft: ModelSourceDraft,
  initialDraft: ModelSourceDraft,
): ModelDraftChangeFlags {
  return {
    contextWindow: draft.contextWindow !== initialDraft.contextWindow,
    maxOutputTokens: draft.maxOutputTokens !== initialDraft.maxOutputTokens,
    inputPer1M: draft.inputPer1M !== initialDraft.inputPer1M,
    cachedInputPer1M: draft.cachedInputPer1M !== initialDraft.cachedInputPer1M,
    outputPer1M: draft.outputPer1M !== initialDraft.outputPer1M,
    audioPerMinute: draft.audioPerMinute !== initialDraft.audioPerMinute,
    supportsStreaming: draft.supportsStreaming !== initialDraft.supportsStreaming,
    supportsTools: draft.supportsTools !== initialDraft.supportsTools,
    supportsVision: draft.supportsVision !== initialDraft.supportsVision,
    supportsReasoning:
      draft.supportsReasoning !== initialDraft.supportsReasoning ||
      JSON.stringify(draft.reasoningEfforts) !== JSON.stringify(initialDraft.reasoningEfforts) ||
      draft.defaultReasoningEffort !== initialDraft.defaultReasoningEffort,
    toolTypes: Object.fromEntries(
      SOURCE_TOOL_TYPES.filter((type) => draft.toolTypes[type] !== initialDraft.toolTypes[type]).map((type) => [
        type,
        draft.toolTypes[type],
      ]),
    ),
  };
}

function hasAnyModelDraftChange(flags: ModelDraftChangeFlags): boolean {
  return Object.values(flags).some((flag) => (typeof flag === "boolean" ? flag : Object.keys(flag).length > 0));
}

// A row with no stored model takes every current source-wide setting.
function newRowChangeFlags(draft: ModelSourceDraft): ModelDraftChangeFlags {
  return {
    contextWindow: true,
    maxOutputTokens: true,
    inputPer1M: true,
    cachedInputPer1M: true,
    outputPer1M: true,
    audioPerMinute: true,
    supportsStreaming: true,
    supportsTools: true,
    supportsVision: true,
    supportsReasoning: true,
    toolTypes: draft.toolTypes,
  };
}

function rowSignature(rows: ModelRow[]): string {
  return JSON.stringify(
    rows.map((row) => [row.model.trim(), row.upstreamModel.trim(), row.isEnabled, row.subagentsAllowed, row.originModel]),
  );
}

function buildModelInputs(
  rows: ModelRow[],
  draft: ModelSourceDraft,
  draftChangeFlags: ModelDraftChangeFlags,
  existingModelsByName: Map<string, ModelSourceModel>,
): ModelSourceModelInput[] {
  return rows.map((row) => {
    const model = row.model.trim();
    const upstreamModel = row.upstreamModel.trim();
    // Rows remember the stored model they came from; pasted aliases fall back
    // to an existing model named by their upstream target.
    const existingModel =
      (row.originModel ? existingModelsByName.get(row.originModel) : undefined) ??
      existingModelsByName.get(model) ??
      (upstreamModel ? existingModelsByName.get(upstreamModel) : undefined);
    const flags = existingModel ? draftChangeFlags : newRowChangeFlags(draft);

    let rawMetadataJson = existingModel?.rawMetadataJson ?? null;
    if (flags.supportsReasoning) {
      rawMetadataJson = mergeReasoningMetadata(
        rawMetadataJson,
        draft.supportsReasoning,
        draft.reasoningEfforts,
        draft.defaultReasoningEffort,
      );
    }
    rawMetadataJson = mergeToolTypeMetadata(rawMetadataJson, flags.toolTypes);
    rawMetadataJson = mergeSubagentMetadata(rawMetadataJson, row.subagentsAllowed);

    return {
      model,
      displayName:
        existingModel?.displayName && existingModel.displayName !== existingModel.model
          ? existingModel.displayName
          : model,
      contextWindow: flags.contextWindow ? parsePositiveInt(draft.contextWindow) : existingModel?.contextWindow ?? null,
      maxOutputTokens: flags.maxOutputTokens
        ? parsePositiveInt(draft.maxOutputTokens)
        : existingModel?.maxOutputTokens ?? null,
      supportsStreaming: flags.supportsStreaming ? draft.supportsStreaming : existingModel?.supportsStreaming ?? true,
      supportsTools: flags.supportsTools ? draft.supportsTools : existingModel?.supportsTools ?? false,
      supportsVision: flags.supportsVision ? draft.supportsVision : existingModel?.supportsVision ?? false,
      inputPer1M: flags.inputPer1M ? parseNonNegativeFloat(draft.inputPer1M) : existingModel?.inputPer1M ?? null,
      cachedInputPer1M: flags.cachedInputPer1M
        ? parseNonNegativeFloat(draft.cachedInputPer1M)
        : existingModel?.cachedInputPer1M ?? null,
      outputPer1M: flags.outputPer1M ? parseNonNegativeFloat(draft.outputPer1M) : existingModel?.outputPer1M ?? null,
      audioPerMinute: flags.audioPerMinute
        ? parseNonNegativeFloat(draft.audioPerMinute)
        : existingModel?.audioPerMinute ?? null,
      rawMetadataJson: mergeUpstreamModelMetadata(rawMetadataJson, upstreamModel || undefined),
      isEnabled: row.isEnabled,
    };
  });
}

export type ModelSourceEditDialogProps = {
  open: boolean;
  busy: boolean;
  source: ModelSource | null;
  onOpenChange: (open: boolean) => void;
  onSubmit: (sourceId: string, payload: ModelSourceUpdateRequest) => Promise<void>;
};

type ModelSourceEditFormProps = {
  source: ModelSource;
  busy: boolean;
  onSubmit: (sourceId: string, payload: ModelSourceUpdateRequest) => Promise<void>;
  onClose: () => void;
};

function ModelSourceEditForm({ source, busy, onSubmit, onClose }: ModelSourceEditFormProps) {
  const { t } = useTranslation();
  const form = useForm<ModelSourceFormValues>({
    resolver: zodResolver(createModelSourceFormSchema(t)),
    defaultValues: {
      name: source.name,
      baseUrl: source.baseUrl,
      apiKey: "",
      models: modelRowsFromSource(source),
    },
  });
  const [draft, updateDraft] = useReducer(modelSourceDraftReducer, source, draftFromSource);
  const lockedToolTypes = sourceToolTypeStates(source.models).locked;

  const handleSubmit = async (values: ModelSourceFormValues) => {
    const draftChangeFlags = getModelDraftChangeFlags(draft, draftFromSource(source));
    const modelRowsChanged = rowSignature(values.models) !== rowSignature(modelRowsFromSource(source));

    const payload: ModelSourceUpdateRequest = {
      name: values.name,
      baseUrl: values.baseUrl,
      supportsChatCompletions: draft.supportsChatCompletions,
      supportsResponses: draft.supportsResponses,
      supportsResponsesWebsocket: draft.supportsResponsesWebsocket,
      supportsAudioTranscriptions: draft.supportsAudioTranscriptions,
      supportsEmbeddings: draft.supportsEmbeddings,
    };

    if (modelRowsChanged || hasAnyModelDraftChange(draftChangeFlags)) {
      const existingModelsByName = new Map(source.models.map((model) => [model.model, model]));
      payload.models = buildModelInputs(values.models, draft, draftChangeFlags, existingModelsByName);
    }

    // The stored key is never returned, so a blank field means "keep it";
    // only a typed value updates the credential.
    const apiKey = values.apiKey.trim();
    if (apiKey) {
      payload.apiKey = apiKey;
    }
    try {
      await onSubmit(source.id, payload);
    } catch {
      return;
    }
    onClose();
  };

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
        <ModelSourceFormFields
          control={form.control}
          draft={draft}
          updateDraft={updateDraft}
          lockedToolTypes={lockedToolTypes}
	          apiKeyLabel={t("modelSources.fields.upstreamApiKey")}
	          apiKeyPlaceholder={t("modelSources.editDialog.keepCurrentKey")}
        />
        <DialogFooter>
          <Button type="submit" disabled={busy || form.formState.isSubmitting}>
	            {t("common.actions.save")}
          </Button>
        </DialogFooter>
      </form>
    </Form>
  );
}

export function ModelSourceEditDialog({
  open,
  busy,
  source,
  onOpenChange,
  onSubmit,
}: ModelSourceEditDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[calc(100dvh-2rem)] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
	          <DialogTitle>{t("modelSources.editDialog.title")}</DialogTitle>
	          <DialogDescription>{t("modelSources.editDialog.description")}</DialogDescription>
        </DialogHeader>

        {source ? (
          <ModelSourceEditForm
            key={`${source.id}:${open ? "open" : "closed"}`}
            source={source}
            busy={busy}
            onSubmit={onSubmit}
            onClose={() => onOpenChange(false)}
          />
        ) : (
	          <p className="text-sm text-muted-foreground">{t("modelSources.editDialog.selectSource")}</p>
        )}
      </DialogContent>
    </Dialog>
  );
}
