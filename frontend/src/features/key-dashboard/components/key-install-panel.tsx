import { Check, Download, FileCode2, FolderSync, Globe2, Info, KeyRound, Monitor, PanelsTopLeft, RotateCw, ShieldCheck, Terminal, TriangleAlert } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { AlertMessage } from "@/components/alert-message";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { CopyButton } from "@/components/copy-button";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { SpinnerBlock } from "@/components/ui/spinner";
import { getInstallScript, type InstallPlatform } from "@/features/key-dashboard/api";
import { downloadInstallScript, installCommand, uninstallCommand } from "@/features/key-dashboard/install";
import { ApiError } from "@/lib/api-client";

type KeyInstallPanelProps = {
  apiKey: string;
  onUnauthorized: () => void;
};

const PLATFORMS = [
  { value: "macos", label: "macOS", icon: Monitor },
  { value: "linux", label: "Linux", icon: Terminal },
  { value: "windows", label: "Windows", icon: PanelsTopLeft },
] as const;

const GUIDANCE = [
  { icon: FolderSync, title: "keyDashboard.install.backupTitle", notice: "keyDashboard.install.backupNotice" },
  { icon: RotateCw, title: "keyDashboard.install.restartTitle", notice: "keyDashboard.install.restartNotice" },
  { icon: Globe2, title: "keyDashboard.install.environmentTitle", notice: "keyDashboard.install.environmentNotice" },
] as const;

export function KeyInstallPanel({ apiKey, onUnauthorized }: KeyInstallPanelProps) {
  const { t } = useTranslation();
  const [platform, setPlatform] = useState<InstallPlatform>("macos");
  const [keepLogin, setKeepLogin] = useState(true);

  return (
    <section className="space-y-6" aria-labelledby="key-install-heading">
      <div className="space-y-1.5">
        <h2 id="key-install-heading" className="text-xl font-semibold tracking-tight">{t("keyDashboard.install.title")}</h2>
        <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{t("keyDashboard.install.description")}</p>
        <p className="text-xs text-muted-foreground">{t("keyDashboard.install.worksWith")}</p>
      </div>

      <section aria-labelledby="key-install-prerequisite" className="flex gap-3 rounded-xl border border-sky-500/20 bg-sky-500/5 p-4">
        <Info className="mt-0.5 size-4 shrink-0 text-sky-700 dark:text-sky-400" aria-hidden="true" />
        <div className="space-y-1">
          <h3 id="key-install-prerequisite" className="text-sm font-semibold">{t("keyDashboard.install.beforeRun")}</h3>
          <p className="text-sm leading-relaxed text-muted-foreground">{t("keyDashboard.install.prerequisite")}</p>
        </div>
      </section>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 overflow-hidden rounded-xl border bg-card">
          <div className="space-y-6 p-5 sm:p-6">
            <fieldset>
              <legend className="mb-3 flex items-center gap-3 text-sm font-semibold">
                <StepNumber value={1} />
                {t("keyDashboard.install.platform")}
              </legend>
              <div className="grid grid-cols-3 gap-2">
                {PLATFORMS.map((item) => (
                  <label key={item.value} className="relative min-w-0 cursor-pointer">
                    <input
                      type="radio"
                      name="install-platform"
                      className="peer sr-only"
                      aria-label={item.label}
                      value={item.value}
                      checked={platform === item.value}
                      onChange={() => setPlatform(item.value)}
                    />
                    <span className="flex min-h-11 items-center justify-center gap-2 rounded-lg border px-2 py-2 text-sm font-semibold text-muted-foreground transition-colors hover:bg-muted/50 peer-checked:border-sky-500 peer-checked:bg-sky-500/5 peer-checked:text-sky-700 peer-focus-visible:ring-2 peer-focus-visible:ring-ring peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background dark:peer-checked:text-sky-400">
                      <item.icon className="hidden size-4 shrink-0 sm:block" aria-hidden="true" />
                      <span className="truncate">{item.label}</span>
                      {platform === item.value ? <Check className="absolute top-1 right-1 size-3" aria-hidden="true" /> : null}
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="space-y-3 border-t pt-6">
              <h3 className="flex items-center gap-3 text-sm font-semibold">
                <StepNumber value={2} />
                {t("keyDashboard.install.options")}
              </h3>
              <div className="flex items-start gap-3">
                <Checkbox
                  id="install-keep-login"
                  className="mt-0.5"
                  checked={keepLogin}
                  aria-describedby="install-keep-login-description"
                  onCheckedChange={(checked) => setKeepLogin(checked === true)}
                />
                <div className="space-y-1">
                  <label htmlFor="install-keep-login" className="cursor-pointer text-sm font-medium">{t("keyDashboard.install.keepLogin")}</label>
                  <p id="install-keep-login-description" className="text-xs leading-relaxed text-muted-foreground">{t("keyDashboard.install.keepLoginDescription")}</p>
                </div>
              </div>
              {keepLogin ? <KeepLoginWarning /> : null}
            </div>
          </div>
          <InstallerActions
            key={`${platform}-${keepLogin}`}
            platform={platform}
            keepLogin={keepLogin}
            apiKey={apiKey}
            onUnauthorized={onUnauthorized}
            restore={<RestoreSetup platform={platform} />}
          />
        </div>

        <aside className="min-w-0 space-y-4" aria-labelledby="key-install-guidance">
          <div className="rounded-xl border bg-card p-5">
            <h3 id="key-install-guidance" className="text-sm font-semibold">{t("keyDashboard.install.notes")}</h3>
            <div className="mt-4 space-y-5">
              {GUIDANCE.map((item) => (
                <div key={item.title} className="flex gap-3">
                  <item.icon className="mt-0.5 size-4 shrink-0 text-sky-700 dark:text-sky-400" aria-hidden="true" />
                  <div className="space-y-1.5">
                    <h4 className="text-xs font-semibold">{t(item.title)}</h4>
                    <p className="text-xs leading-relaxed text-muted-foreground">{t(item.notice)}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-5">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-800 dark:text-amber-300">
              <ShieldCheck className="size-4 shrink-0" aria-hidden="true" />
              {t("keyDashboard.install.secretTitle")}
            </h3>
            <p className="mt-2 text-xs leading-relaxed text-amber-800/90 dark:text-amber-200/80">{t("keyDashboard.install.secretNotice")}</p>
          </div>
        </aside>
      </div>
    </section>
  );
}

function StepNumber({ value }: { value: number }) {
  return (
    <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-sky-500/10 text-xs text-sky-700 dark:text-sky-400" aria-hidden="true">
      {value}
    </span>
  );
}

function RestoreSetup({ platform }: { platform: InstallPlatform }) {
  const { t } = useTranslation();
  return (
    <div className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="text-sm font-semibold">{t("keyDashboard.install.uninstallTitle")}</h4>
        <CopyButton key={platform} value={uninstallCommand(platform)} label={t("keyDashboard.install.copyUninstall")} />
      </div>
      <p className="text-xs leading-relaxed text-muted-foreground">{t("keyDashboard.install.uninstallNotice")}</p>
      <code className="block rounded-lg border bg-background px-3 py-2.5 text-xs leading-relaxed [overflow-wrap:anywhere]">{uninstallCommand(platform)}</code>
    </div>
  );
}

function KeepLoginWarning() {
  const { t } = useTranslation();
  return (
    <div role="note" className="rounded-lg border-2 border-red-500/60 bg-red-500/10 p-4 text-red-900 dark:text-red-200">
      <p className="flex items-center gap-2 text-sm font-bold">
        <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
        {t("keyDashboard.install.keepLoginWarningTitle")}
      </p>
      <p className="mt-2 text-sm leading-relaxed">{t("keyDashboard.install.keepLoginWarning")}</p>
    </div>
  );
}

type ExportConfirmation = (result: HTMLElement | null | false) => void;

function InstallerActions({
  platform,
  keepLogin,
  apiKey,
  onUnauthorized,
  restore,
}: KeyInstallPanelProps & { platform: InstallPlatform; keepLogin: boolean; restore: ReactNode }) {
  const { t } = useTranslation();
  const [script, setScript] = useState<string | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const pendingConfirmation = useRef<ExportConfirmation | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void getInstallScript(apiKey, platform, keepLogin, controller.signal).then((result) => {
      if (!controller.signal.aborted) setScript(result);
    }).catch((caught: unknown) => {
      if (controller.signal.aborted) return;
      if (caught instanceof ApiError && caught.status === 401) {
        onUnauthorized();
      } else {
        setError(true);
      }
    });
    return () => controller.abort();
  }, [apiKey, platform, keepLogin, onUnauthorized, attempt]);

  const settleConfirmation = (result: HTMLElement | null | false) => {
    pendingConfirmation.current?.(result);
    pendingConfirmation.current = null;
    setConfirming(false);
  };
  // Exports that send the login access token require an explicit, warned confirmation.
  const confirmExport = keepLogin
    ? () => new Promise<HTMLElement | null | false>((resolve) => {
        // A newer export request cancels any still-pending one instead of leaving it unresolved.
        pendingConfirmation.current?.(false);
        pendingConfirmation.current = resolve;
        setConfirming(true);
      })
    : undefined;
  const shell = platform === "windows" ? "PowerShell" : "Bash";
  const filename = `codex-lb-${platform}.${platform === "windows" ? "ps1" : "sh"}`;
  const ready = !error && script !== null;

  let commandBody: ReactNode;
  if (error) {
    commandBody = (
      <div className="space-y-3">
        <AlertMessage variant="error">{t("keyDashboard.install.loadFailed")}</AlertMessage>
        <Button variant="outline" onClick={() => { setError(false); setAttempt(attempt + 1); }}>
          {t("keyDashboard.refresh")}
        </Button>
      </div>
    );
  } else if (script === null) {
    commandBody = <SpinnerBlock />;
  } else {
    commandBody = (
      <>
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 text-slate-200">
          <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3 text-xs font-medium text-slate-400">
            <Terminal className="size-3.5" aria-hidden="true" />
            <span>{shell}</span>
          </div>
          <pre className="p-4 text-xs leading-7 whitespace-pre-wrap [overflow-wrap:anywhere] sm:p-5 sm:text-[13px]"><code>{installCommand(platform, "YOUR_API_KEY", window.location.origin, keepLogin)}</code></pre>
        </div>
        <p className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
          <KeyRound className="mt-0.5 size-3.5 shrink-0 text-sky-700 dark:text-sky-400" aria-hidden="true" />
          {t("keyDashboard.install.maskedNotice")}
        </p>
      </>
    );
  }

  const download = async () => {
    if (script === null) return;
    if (confirmExport && (await confirmExport()) === false) return;
    downloadInstallScript(script, platform);
  };

  return (
    <>
      <div className="space-y-4 border-t p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="flex items-center gap-3 text-sm font-semibold">
            <StepNumber value={3} />
            {t("keyDashboard.install.directCommand")}
          </h3>
          {ready ? (
            <div className="max-sm:w-full [&_button]:h-9 [&_button]:border-sky-700 [&_button]:bg-sky-700 [&_button]:text-white [&_button]:max-sm:w-full [&_button]:dark:bg-sky-700 [&_button:hover]:bg-sky-800 [&_button:hover]:dark:bg-sky-800">
              <CopyButton value={installCommand(platform, apiKey, window.location.origin, keepLogin)} label={t("keyDashboard.install.copyCommand")} confirm={confirmExport} />
            </div>
          ) : null}
        </div>
        {commandBody}
      </div>

      <div className="space-y-4 border-t bg-muted/30 p-5 sm:p-6">
        <h3 className="text-sm font-semibold">{t("keyDashboard.install.otherWays")}</h3>
        <div className="grid gap-6 md:grid-cols-2">
          {ready ? (
            <div className="min-w-0 space-y-3">
              <div className="flex min-w-0 items-center gap-3">
                <div className="rounded-lg bg-background p-2 text-muted-foreground"><FileCode2 className="size-4" aria-hidden="true" /></div>
                <div className="min-w-0 space-y-0.5">
                  <h4 className="text-sm font-semibold">{t("keyDashboard.install.scriptFile")}</h4>
                  <p className="font-mono text-xs text-muted-foreground [overflow-wrap:anywhere]">{filename}</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <CopyButton value={script} label={t("keyDashboard.install.copyScript")} confirm={confirmExport} />
                <Button variant="outline" size="sm" onClick={() => void download()}>
                  <Download className="size-4" aria-hidden="true" />
                  {t("keyDashboard.install.downloadScript")}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">{t("keyDashboard.install.runFile")}</p>
              <code className="block rounded-lg border bg-background px-3 py-2.5 text-xs leading-relaxed [overflow-wrap:anywhere]">
                {platform === "windows" ? "powershell -ExecutionPolicy Bypass -File .\\codex-lb-windows.ps1" : `bash ${filename}`}
              </code>
              <details className="overflow-hidden rounded-lg border bg-background text-xs">
                <summary className="cursor-pointer px-4 py-3 font-medium transition-colors hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring">{t("keyDashboard.install.previewScript")}</summary>
                <pre tabIndex={0} aria-label={t("keyDashboard.install.previewScript")} className="max-h-80 overflow-auto border-t bg-muted/30 p-4 leading-relaxed focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring"><code>{script.replaceAll(apiKey, "YOUR_API_KEY")}</code></pre>
              </details>
            </div>
          ) : null}
          {restore}
        </div>
      </div>
      <ConfirmDialog
        open={confirming}
        title={t("keyDashboard.install.keepLoginConfirmTitle")}
        description={t("keyDashboard.install.keepLoginConfirmDescription")}
        confirmLabel={t("keyDashboard.install.keepLoginConfirmAction")}
        onConfirm={(event) => settleConfirmation(event.currentTarget.closest<HTMLElement>("[role='alertdialog']"))}
        onOpenChange={(open) => {
          if (!open) settleConfirmation(false);
        }}
      >
        <KeepLoginWarning />
      </ConfirmDialog>
    </>
  );
}
