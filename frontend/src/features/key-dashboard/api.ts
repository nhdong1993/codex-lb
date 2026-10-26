import { z } from "zod";

import { ApiError, get } from "@/lib/api-client";
import {
  KeyDashboardGroupSchema,
  KeyDashboardProfileSchema,
  KeyDashboardRequestLogsResponseSchema,
  KeyUsageSchema,
  type KeyDashboardProfile,
  type KeyDashboardRequestLogsResponse,
  type KeyUsage,
} from "@/features/key-dashboard/schemas";

export function getKeyDashboardGroup(apiKey: string, signal: AbortSignal) {
  return get("/api/key-dashboard/group", KeyDashboardGroupSchema, { ...keyRequestOptions(apiKey), signal });
}

export type InstallPlatform = "macos" | "linux" | "windows";

export function installScriptPath(platform: InstallPlatform, protocol: string, keepLogin: boolean): string {
  const params = new URLSearchParams({ platform });
  if (protocol === "https:") params.set("scheme", "https");
  if (keepLogin) params.set("keep_login", "true");
  return `/api/key-dashboard/install-script?${params.toString()}`;
}

export function getInstallScript(
  apiKey: string,
  platform: InstallPlatform,
  keepLogin: boolean,
  signal: AbortSignal,
): Promise<string> {
  const options = keyRequestOptions(apiKey);
  return get(installScriptPath(platform, window.location.protocol, keepLogin), z.string(), {
    ...options,
    headers: { ...options.headers, Accept: "text/plain" },
    signal,
  });
}

function keyRequestOptions(apiKey: string) {
  return {
    headers: { Authorization: `Bearer ${apiKey}` },
    credentials: "omit" as const,
    cache: "no-store" as const,
    suppressUnauthorizedHandler: true,
  };
}

export function getKeyUsage(apiKey: string): Promise<KeyUsage> {
  return get("/v1/usage", KeyUsageSchema, keyRequestOptions(apiKey));
}

export function getKeyDashboardProfile(apiKey: string): Promise<KeyDashboardProfile> {
  return get(
    "/api/key-dashboard/profile",
    KeyDashboardProfileSchema,
    keyRequestOptions(apiKey),
  );
}

export function getKeyDashboardRequestLogs(
  apiKey: string,
  limit: number,
  offset: number,
): Promise<KeyDashboardRequestLogsResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  return get(
    `/api/key-dashboard/request-logs?${params.toString()}`,
    KeyDashboardRequestLogsResponseSchema,
    keyRequestOptions(apiKey),
  );
}

export async function getKeyDashboardData(
  apiKey: string,
  limit: number,
  offset: number,
  includeLogs = true,
  onUnauthorized?: () => void,
): Promise<{
  profile: KeyDashboardProfile;
  usage: KeyUsage;
  logs: KeyDashboardRequestLogsResponse | null;
}> {
  const requests = [
    getKeyDashboardProfile(apiKey),
    getKeyUsage(apiKey),
    includeLogs ? getKeyDashboardRequestLogs(apiKey, limit, offset) : Promise.resolve(null),
  ] as const;
  // Report every 401, even one arriving after another failure already rejected the batch, so a revoked key always disconnects.
  for (const request of requests) {
    request.catch((reason: unknown) => {
      if (reason instanceof ApiError && reason.status === 401) onUnauthorized?.();
    });
  }
  const [profile, usage, logs] = await Promise.all(requests);
  return { profile, usage, logs };
}
