import { useTranslation } from "react-i18next";

import { Checkbox } from "@/components/ui/checkbox";
import {
  SOURCE_TOOL_TYPES,
  type ModelSourceDraft,
  type SourceToolType,
  type SourceToolTypeFlags,
} from "@/features/model-sources/components/model-source-form";

const TOOL_TYPE_TEXT = {
  namespace: { labelKey: "modelSources.tools.namespace", wireType: "namespace" },
  custom: { labelKey: "modelSources.tools.applyPatch", wireType: "custom · freeform" },
  web_search: { labelKey: "modelSources.tools.webSearch", wireType: "web_search" },
} as const satisfies Record<SourceToolType, { labelKey: string; wireType: string }>;

type SourceToolForwardingFieldsProps = {
  draft: ModelSourceDraft;
  updateDraft: (patch: Partial<ModelSourceDraft>) => void;
  lockedToolTypes?: SourceToolTypeFlags;
};

export function SourceToolForwardingFields({ draft, updateDraft, lockedToolTypes }: SourceToolForwardingFieldsProps) {
  const { t } = useTranslation();
  return (
    <div className="space-y-3 rounded-md border p-3">
      <div>
        <div className="text-sm font-medium">{t("modelSources.tools.title")}</div>
        <p className="text-xs text-muted-foreground">{t("modelSources.tools.description")}</p>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <Checkbox
          checked={draft.supportsTools}
          onCheckedChange={(checked) => updateDraft({ supportsTools: checked === true })}
        />
        {t("modelSources.capabilities.tools")}
      </label>

      <div className="grid gap-2 sm:grid-cols-2">
        <div className="flex items-start gap-2 rounded-md border p-2 text-sm">
          <Checkbox className="mt-0.5" checked disabled aria-label={t("modelSources.tools.function")} />
          <span>
            <span className="block">{t("modelSources.tools.function")}</span>
            <span className="block text-xs text-muted-foreground">{t("modelSources.tools.functionHint")}</span>
          </span>
        </div>
        {SOURCE_TOOL_TYPES.map((type) => {
          const locked = lockedToolTypes?.[type] ?? false;
          const label = t(TOOL_TYPE_TEXT[type].labelKey);
          return (
            <label key={type} className="flex items-start gap-2 rounded-md border p-2 text-sm">
              <Checkbox
                className="mt-0.5"
                aria-label={label}
                checked={draft.toolTypes[type]}
                disabled={locked}
                onCheckedChange={(checked) =>
                  updateDraft({
                    toolTypes: { ...draft.toolTypes, [type]: checked === true },
                    ...(checked === true ? { supportsTools: true } : {}),
                  })
                }
              />
              <span>
                <span className="block">{label}</span>
                <span className="block font-mono text-xs text-muted-foreground">{TOOL_TYPE_TEXT[type].wireType}</span>
                {locked ? (
                  <span className="block text-xs text-muted-foreground">{t("modelSources.tools.locked")}</span>
                ) : null}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}
