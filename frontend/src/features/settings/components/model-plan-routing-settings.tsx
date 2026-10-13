import { useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useModels } from "@/features/api-keys/hooks/use-models";
import { AccountRoutingPlanSchema, type ModelPlanRoutingPolicies } from "@/features/settings/schemas";

export function ModelPlanRoutingSettings({
  policies,
  busy,
  onSave,
}: {
  policies: ModelPlanRoutingPolicies;
  busy: boolean;
  onSave: (policies: ModelPlanRoutingPolicies) => Promise<void>;
}) {
  const { t } = useTranslation();
  const models = useModels();
  const [model, setModel] = useState("");
  const [plans, setPlans] = useState<ModelPlanRoutingPolicies[string]>(["free"]);
  const nativeIds = new Set(
    models.data?.filter((item) => !item.sourceOnly && !item.imageOnly).map((item) => item.id),
  );
  // Saved IDs remain editable even when the catalog stops advertising them as
  // native (absent, or now listed only as source-only or image-only).
  const missingSavedIds = Object.keys(policies).filter((id) => !nativeIds.has(id));
  const modelIds = [...nativeIds, ...missingSavedIds].sort();

  const save = async (next: ModelPlanRoutingPolicies) => {
    try {
      await onSave(next);
      setModel("");
      setPlans(["free"]);
    } catch {
      // The settings mutation owns the error toast and conflict refetch.
      // Keep the draft on failure; refreshed policy props reset it in the parent.
    }
  };

  return (
    <section className="space-y-3 p-3" aria-label={t("settings.routing.modelPlans.title")}>
      <div>
        <p className="text-sm font-medium">{t("settings.routing.modelPlans.title")}</p>
        <p className="text-xs text-muted-foreground">{t("settings.routing.modelPlans.description")}</p>
      </div>
      {Object.entries(policies).map(([id, allowed]) => (
        <div key={id} className="flex flex-wrap items-center gap-2 rounded-md border p-2 text-xs">
          <span className="min-w-0 flex-1 break-all font-mono">{id}</span>
          <span>{allowed.join(", ")}</span>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            aria-label={t("settings.routing.modelPlans.editAria", {
              model: id,
            })}
            onClick={() => {
              setModel(id);
              setPlans(allowed);
            }}
          >
            {t("settings.routing.modelPlans.edit")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            aria-label={t("settings.routing.modelPlans.removeAria", {
              model: id,
            })}
            onClick={() => {
              const next = { ...policies };
              delete next[id];
              void save(next);
            }}
          >
            {t("settings.routing.modelPlans.remove")}
          </Button>
        </div>
      ))}
      {Object.keys(policies).length === 0 && (
        <p className="text-xs text-muted-foreground">{t("settings.routing.modelPlans.empty")}</p>
      )}
      {models.isLoading && (
        <p role="status" className="text-xs">
          {t("settings.routing.modelPlans.loading")}
        </p>
      )}
      {models.isError && (
        <p role="alert" className="text-xs text-destructive">
          {t("settings.routing.modelPlans.error")}
        </p>
      )}
      <Select
        value={model}
        disabled={busy || modelIds.length === 0}
        onValueChange={(id) => {
          setModel(id);
          setPlans(policies[id] ?? ["free"]);
        }}
      >
        <SelectTrigger className="w-full" aria-label={t("settings.routing.modelPlans.model")}>
          <SelectValue placeholder={t("settings.routing.modelPlans.model")}>{model || undefined}</SelectValue>
        </SelectTrigger>
        <SelectContent>
          {modelIds.map((id) => (
            <SelectItem key={id} value={id}>
              {id}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <fieldset disabled={busy} className="flex flex-wrap gap-x-4 gap-y-2">
        <legend className="mb-2 text-xs font-medium">{t("settings.routing.modelPlans.plans")}</legend>
        {AccountRoutingPlanSchema.options.map((plan) => (
          <label key={plan} className="flex items-center gap-1.5 text-xs">
            <Checkbox
              checked={plans.includes(plan)}
              disabled={busy}
              onCheckedChange={(checked) =>
                setPlans((current) => (checked ? [...current, plan] : current.filter((item) => item !== plan)))
              }
            />
            {plan}
          </label>
        ))}
      </fieldset>
      <Button
        size="sm"
        variant="outline"
        disabled={busy || !model || plans.length === 0}
        onClick={() => void save({ ...policies, [model]: plans })}
      >
        {t("settings.routing.modelPlans.save")}
      </Button>
    </section>
  );
}
