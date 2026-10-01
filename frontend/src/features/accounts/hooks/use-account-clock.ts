import { createContext, useContext, useState } from "react";

export const AccountClock = createContext<number | null>(null);

export function useAccountClock() {
  const [mountedAt] = useState(Date.now);
  return useContext(AccountClock) ?? mountedAt;
}
