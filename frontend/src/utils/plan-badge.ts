const PLAN_BADGE_CLASS_MAP: Record<string, string> = {
  free: "bg-zinc-500/10 text-zinc-700 border-zinc-500/20 hover:bg-zinc-500/15 dark:text-zinc-300",
  go: "bg-lime-500/15 text-lime-700 border-lime-500/25 hover:bg-lime-500/20 dark:text-lime-300",
  plus: "bg-emerald-500/15 text-emerald-700 border-emerald-500/20 hover:bg-emerald-500/20 dark:text-emerald-400",
  team: "bg-sky-500/15 text-sky-700 border-sky-500/20 hover:bg-sky-500/20 dark:text-sky-300",
  business: "bg-blue-500/15 text-blue-700 border-blue-500/20 hover:bg-blue-500/20 dark:text-blue-300",
  enterprise: "bg-indigo-500/15 text-indigo-700 border-indigo-500/20 hover:bg-indigo-500/20 dark:text-indigo-300",
  edu: "bg-teal-500/15 text-teal-700 border-teal-500/20 hover:bg-teal-500/20 dark:text-teal-300",
  pro: "bg-violet-500/15 text-violet-700 border-violet-500/20 hover:bg-violet-500/20 dark:text-violet-300",
  prolite: "bg-amber-500/15 text-amber-700 border-amber-500/25 hover:bg-amber-500/20 dark:text-amber-300",
  promax: "bg-fuchsia-500/15 text-fuchsia-700 border-fuchsia-500/25 hover:bg-fuchsia-500/20 dark:text-fuchsia-300",
};

export function planBadgeClass(planType: string): string {
  return PLAN_BADGE_CLASS_MAP[planType.trim().toLowerCase()] ?? PLAN_BADGE_CLASS_MAP.free;
}
