import { describe, expect, it } from "vitest";

import { createAccountSummary } from "@/test/mocks/factories";
import { mergeAccountSnapshot, mergeSubscriptionRefresh } from "./subscription-refresh";

describe("plan verification and delayed subscription responses", () => {
  it("keeps current pending verification when a manual subscription result arrives", () => {
    const current = createAccountSummary({ planCheckPending: true });
    const incoming = { ...current, planCheckPending: false };
    expect(mergeSubscriptionRefresh(current, incoming).planCheckPending).toBe(true);
  });

  it("lets a current poll complete verification even while retaining a newer compatible term", () => {
    const current = createAccountSummary({ planCheckPending: true,
      subscription: { activeUntil: null, lastCheckedAt: "2026-10-02T08:48:00Z" },
    });
    const incoming = { ...current, planCheckPending: false,
      subscription: { activeUntil: "2026-10-04T05:54:59Z", lastCheckedAt: "2026-10-02T04:11:00Z" },
    };
    const merged = mergeAccountSnapshot(current, incoming);
    expect(merged.planCheckPending).toBe(false);
    expect(merged.subscription?.activeUntil).toBeNull();
  });
});
