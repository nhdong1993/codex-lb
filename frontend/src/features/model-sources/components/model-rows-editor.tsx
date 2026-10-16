import { useState } from "react";
import { ClipboardList, Plus, Search, Trash2 } from "lucide-react";
import { useFieldArray, useFormState, useWatch, type Control } from "react-hook-form";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { FormControl, FormField, FormItem, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  bulkModelRows,
  newModelRow,
  parseBulkModelEntries,
  type ModelSourceFormValues,
} from "@/features/model-sources/components/model-source-form";

const FILTER_MIN_ROWS = 6;
// Fixed switch/button columns keep the header aligned with every row.
const ROW_GRID = "grid grid-cols-[2.25rem_minmax(0,1fr)_minmax(0,1fr)_3.75rem_2rem] gap-2";
const BULK_INPUT_ID = "model-source-bulk-models";

type ModelRowsEditorProps = {
  control: Control<ModelSourceFormValues>;
};

export function ModelRowsEditor({ control }: ModelRowsEditorProps) {
  const { t } = useTranslation();
  const { fields, append, remove } = useFieldArray({ control, name: "models" });
  const rows = useWatch({ control, name: "models" });
  const { errors } = useFormState({ control, name: "models" });
  const [filter, setFilter] = useState("");
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkText, setBulkText] = useState("");
  const [bulkInvalid, setBulkInvalid] = useState(false);

  const needle = filter.trim().toLowerCase();
  const visibleRows = fields
    .map((field, index) => ({ field, index }))
    .filter(({ index }) => {
      const row = rows[index];
      return (
        !needle ||
        (row !== undefined &&
          (row.model.toLowerCase().includes(needle) || row.upstreamModel.toLowerCase().includes(needle)))
      );
    });
  const enabledCount = rows.filter((row) => row.isEnabled).length;
  const listError = errors.models?.root?.message ?? errors.models?.message;

  const addRow = () => {
    setFilter("");
    append(newModelRow());
  };

  const applyBulk = () => {
    const entries = parseBulkModelEntries(bulkText);
    if (!entries) {
      setBulkInvalid(true);
      return;
    }
    // Pasting into a fresh form replaces its untouched blank rows.
    const blankRows = rows.flatMap((row, index) => (!row.model.trim() && row.originModel === null ? [index] : []));
    const added = bulkModelRows(rows, entries);
    remove(blankRows);
    append(added, { shouldFocus: false });
    setFilter("");
    setBulkText("");
    setBulkInvalid(false);
    setBulkOpen(false);
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="text-sm font-medium">{t("modelSources.models.title")}</div>
          <p className="text-xs text-muted-foreground">{t("modelSources.models.description")}</p>
          <p className="text-xs text-muted-foreground">{t("modelSources.models.subagentsDescription")}</p>
        </div>
        <span className="text-xs text-muted-foreground">
          {t("modelSources.models.count", { count: rows.length, enabled: enabledCount })}
        </span>
      </div>

      {/* Stay visible while a filter is active, even after deletions shrink the list. */}
      {fields.length >= FILTER_MIN_ROWS || filter ? (
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder={t("modelSources.models.filter")}
            aria-label={t("modelSources.models.filter")}
            className="pl-8"
            autoComplete="off"
          />
        </div>
      ) : null}

      <div className="rounded-md border">
        <div className={`${ROW_GRID} items-center border-b bg-muted/40 px-2 py-1.5 text-xs font-medium text-muted-foreground`}>
          <span>{t("modelSources.models.enabled")}</span>
          <span>{t("modelSources.models.modelId")}</span>
          <span>{t("modelSources.models.upstreamModel")}</span>
          <span className="leading-tight">{t("modelSources.models.subagents")}</span>
          <span />
        </div>
        <div className="max-h-80 divide-y overflow-y-auto">
          {visibleRows.map(({ field, index }) => {
            const rowLabel = rows[index]?.model.trim() || `#${index + 1}`;
            return (
              <div key={field.id} className={`${ROW_GRID} items-start px-2 py-1.5`}>
                <FormField
                  control={control}
                  name={`models.${index}.isEnabled`}
                  render={({ field: enabledField }) => (
                    <Switch
                      className="mt-2.5"
                      checked={enabledField.value}
                      onCheckedChange={enabledField.onChange}
                      aria-label={t("modelSources.models.enableAria", { model: rowLabel })}
                    />
                  )}
                />
                <FormField
                  control={control}
                  name={`models.${index}.model`}
                  render={({ field: modelField }) => (
                    <FormItem className="gap-1">
                      <FormControl>
                        <Input
                          {...modelField}
                          aria-label={t("modelSources.models.modelIdAria", { index: index + 1 })}
                          placeholder="provider/model"
                          autoComplete="off"
                        />
                      </FormControl>
                      <FormMessage className="text-xs" />
                    </FormItem>
                  )}
                />
                <FormField
                  control={control}
                  name={`models.${index}.upstreamModel`}
                  render={({ field: upstreamField }) => (
                    <FormItem className="gap-1">
                      <FormControl>
                        <Input
                          {...upstreamField}
                          aria-label={t("modelSources.models.upstreamAria", { index: index + 1 })}
                          placeholder={t("modelSources.models.upstreamPlaceholder")}
                          autoComplete="off"
                        />
                      </FormControl>
                      <FormMessage className="text-xs" />
                    </FormItem>
                  )}
                />
                <FormField
                  control={control}
                  name={`models.${index}.subagentsAllowed`}
                  render={({ field: subagentsField }) => (
                    <Switch
                      className="mt-2.5"
                      checked={subagentsField.value}
                      onCheckedChange={subagentsField.onChange}
                      aria-label={t("modelSources.models.subagentsAria", { model: rowLabel })}
                    />
                  )}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="mt-0.5"
                  disabled={fields.length === 1}
                  onClick={() => remove(index)}
                  aria-label={t("modelSources.models.removeAria", { model: rowLabel })}
                >
                  <Trash2 />
                </Button>
              </div>
            );
          })}
          {visibleRows.length === 0 ? (
            <p className="px-2 py-3 text-xs text-muted-foreground">{t("modelSources.models.noMatches")}</p>
          ) : null}
        </div>
      </div>
      {listError ? <p className="text-sm text-destructive">{listError}</p> : null}

      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" size="sm" onClick={addRow}>
          <Plus />
          {t("modelSources.models.add")}
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-expanded={bulkOpen}
          aria-controls={BULK_INPUT_ID}
          onClick={() => setBulkOpen((open) => !open)}
        >
          <ClipboardList />
          {t("modelSources.models.bulkToggle")}
        </Button>
      </div>

      {bulkOpen ? (
        <div className="space-y-2 rounded-md border p-3">
          <label htmlFor={BULK_INPUT_ID} className="block text-xs text-muted-foreground">
            {t("modelSources.models.bulkDescription")}
          </label>
          <textarea
            id={BULK_INPUT_ID}
            value={bulkText}
            onChange={(event) => {
              setBulkText(event.target.value);
              setBulkInvalid(false);
            }}
            aria-invalid={bulkInvalid}
            placeholder={"local-coder\ncd/gpt-6-astra=cd/linxaq"}
            className="border-input placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 aria-invalid:border-destructive min-h-24 w-full rounded-md border bg-transparent px-3 py-2 font-mono text-xs shadow-xs outline-none focus-visible:ring-[3px]"
          />
          {bulkInvalid ? (
            <p className="text-sm text-destructive">{t("modelSources.validation.aliasesInvalid")}</p>
          ) : null}
          <Button type="button" size="sm" onClick={applyBulk} disabled={!bulkText.trim()}>
            {t("modelSources.models.bulkApply")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
