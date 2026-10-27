import { useQuery, useQueryClient } from "@tanstack/react-query";

import { reconcileDashboardQuery, resetReconciliationGeneration } from "@/features/accounts/reset-reconciliation";
import { getDashboardOverview, getDashboardProjections } from "@/features/dashboard/api";
import {
  DEFAULT_OVERVIEW_TIMEFRAME,
  type OverviewTimeframe,
} from "@/features/dashboard/schemas";
import { useDashboardPreferencesStore } from "@/hooks/use-dashboard-preferences";

// Without the weekly pace card the response carries account usage, which the server refreshes every 60 s.
const WITHOUT_WEEKLY_PACE_REFETCH_MS = 60_000;

export function useDashboard(
  timeframe: OverviewTimeframe = DEFAULT_OVERVIEW_TIMEFRAME,
  { weeklyPace = true }: { weeklyPace?: boolean } = {},
) {
  const queryClient = useQueryClient();
  const refreshSeconds = useDashboardPreferencesStore((state) => state.refreshSeconds);
  return useQuery({
    queryKey: weeklyPace ? ["dashboard", "overview", timeframe] : ["dashboard", "overview", timeframe, "without-weekly-pace"],
    queryFn: async () => {
      const generation = resetReconciliationGeneration(queryClient);
      return reconcileDashboardQuery(queryClient, await getDashboardOverview({ timeframe, weeklyPace }), generation);
    },
    refetchInterval: weeklyPace ? refreshSeconds * 1_000 : WITHOUT_WEEKLY_PACE_REFETCH_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}

export function useDashboardProjections(enabled = true) {
  const refreshSeconds = useDashboardPreferencesStore((state) => state.refreshSeconds);
  return useQuery({
    queryKey: ["dashboard", "projections"],
    queryFn: getDashboardProjections,
    enabled,
    refetchInterval: refreshSeconds * 1_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}
