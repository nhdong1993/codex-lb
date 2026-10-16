import { screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";

import type { ModelSource } from "@/features/model-sources/schemas";
import { createModelSource } from "@/test/mocks/factories";
import { server } from "@/test/mocks/server";
import { renderWithProviders } from "@/test/utils";

import { ModelSourcesSettings } from "./model-sources-settings";

type SourceModel = ModelSource["models"][number];

function sourceWithModels(models: Array<Pick<SourceModel, "model" | "contextWindow" | "isEnabled">>): ModelSource {
  const [template] = createModelSource().models;
  return createModelSource({
    name: "ch-relay",
    models: models.map((model, index) => ({ ...template, ...model, id: index + 1, displayName: model.model })),
  });
}

function serveSources(source: ModelSource) {
  server.use(http.get("/api/model-sources/", () => HttpResponse.json({ sources: [source] })));
}

describe("ModelSourcesSettings context window warning", () => {
  it("names enabled models that fall back to the default window", async () => {
    serveSources(
      sourceWithModels([
        { model: "http/gpt-6-astra", contextWindow: null, isEnabled: true },
        { model: "http/gpt-6-sol", contextWindow: 272000, isEnabled: true },
      ]),
    );
    renderWithProviders(<ModelSourcesSettings />);

    expect(
      await screen.findByText(
        "No context window set for http/gpt-6-astra. Codex is told this model accepts 128,000 tokens, so longer threads fail to compact. Set the real window in Edit.",
      ),
    ).toBeInTheDocument();
  });

  it("shows no warning when every enabled model declares a window", async () => {
    serveSources(
      sourceWithModels([
        { model: "http/gpt-6-sol", contextWindow: 272000, isEnabled: true },
        { model: "http/old", contextWindow: null, isEnabled: false },
      ]),
    );
    renderWithProviders(<ModelSourcesSettings />);

    expect(await screen.findByText("http/old")).toBeInTheDocument();
    expect(screen.queryByText(/No context window set/)).not.toBeInTheDocument();
  });
});
