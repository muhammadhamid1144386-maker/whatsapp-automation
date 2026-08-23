import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, CloudOff, RefreshCw, Sheet, Unplug } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { api, clockTime, errText } from "@/lib/api";

export default function GoogleSheets() {
  const [state, setState] = useState(null);
  const [sheetId, setSheetId] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/google-sheets");
      setState(data);
      setSheetId(data.connection.spreadsheet_id || "");
    } catch (e) {
      toast.error(errText(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const connect = async () => {
    setBusy(true);
    try {
      await api.post("/google-sheets/connect", { spreadsheet_id: sheetId.trim(), spreadsheet_name: "Restaurant Data" });
      toast.success("Spreadsheet connected");
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const syncNow = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/google-sheets/sync");
      toast.info(`Processed ${data.processed} jobs · ${data.synced} synced · ${data.failed} failed`);
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    try {
      await api.post("/google-sheets/disconnect");
      toast.success("Disconnected");
      load();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  const connected = state?.connection?.status === "connected";

  return (
    <DashboardLayout title="Google Sheets" subtitle="Business data mirrored out of the database — never the source of truth">
      {!state ? (
        <Skeleton className="h-96 rounded-xl" />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
          <div className="space-y-6">
            <div className="card-surface p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Sync status</p>
                  <p className="mt-2 flex items-center gap-2 font-display text-2xl font-bold">
                    {connected ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                    ) : (
                      <CloudOff className="h-5 w-5 text-muted-foreground" />
                    )}
                    <span data-testid="sheets-status-text">{connected ? "Connected" : "Not connected"}</span>
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {state.connection.spreadsheet_name || "No spreadsheet configured"}
                    {state.connection.last_sync_at && ` · last sync ${clockTime(state.connection.last_sync_at)}`}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button className="rounded-full" disabled={busy} data-testid="sheets-sync-now-btn" onClick={syncNow}>
                    <RefreshCw className="mr-1.5 h-4 w-4" /> Sync now
                  </Button>
                  {connected && (
                    <Button variant="outline" className="rounded-full" data-testid="sheets-disconnect-btn" onClick={disconnect}>
                      <Unplug className="mr-1.5 h-4 w-4" /> Disconnect
                    </Button>
                  )}
                </div>
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-3">
                {[
                  { label: "Pending", value: state.counts.pending, testId: "sheets-count-pending" },
                  { label: "Synced", value: state.counts.synced, testId: "sheets-count-synced" },
                  { label: "Failed", value: state.counts.failed, testId: "sheets-count-failed" },
                ].map((c) => (
                  <div key={c.label} data-testid={c.testId} className="rounded-lg bg-muted/50 p-4">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{c.label}</p>
                    <p className="mt-1 font-display text-2xl font-bold tabular-nums">{c.value}</p>
                  </div>
                ))}
              </div>

              {state.connection.last_error && (
                <p className="mt-4 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive" data-testid="sheets-last-error">
                  {state.connection.last_error}
                </p>
              )}
            </div>

            <div className="card-surface overflow-hidden">
              <div className="border-b px-6 py-4">
                <h2 className="font-display text-lg font-bold">Recent sync jobs</h2>
              </div>
              <div className="max-h-80 divide-y overflow-y-auto scroll-thin" data-testid="sheets-jobs-list">
                {state.jobs.length === 0 && <p className="px-6 py-8 text-center text-sm text-muted-foreground">No jobs queued yet.</p>}
                {state.jobs.map((job) => (
                  <div key={job.id} className="flex items-start gap-3 px-6 py-3 text-sm">
                    <span
                      className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${
                        job.sync_status === "synced" ? "bg-emerald-500" : job.sync_status === "failed" ? "bg-red-500" : "bg-amber-500"
                      }`}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="font-medium">{job.event}</p>
                      <p className="text-xs text-muted-foreground">
                        {job.sync_status} · {job.sync_attempts} attempt(s) · {clockTime(job.created_at)}
                      </p>
                      {job.error_message && <p className="mt-0.5 text-xs text-destructive">{job.error_message}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="card-surface p-6">
              <h2 className="flex items-center gap-2 font-display text-lg font-bold">
                <Sheet className="h-4 w-4" /> Connect a spreadsheet
              </h2>
              <div className="mt-4 space-y-1.5">
                <Label>Spreadsheet ID</Label>
                <Input
                  data-testid="sheets-id-input"
                  value={sheetId}
                  onChange={(e) => setSheetId(e.target.value)}
                  placeholder="1AbC…"
                />
                <p className="text-xs text-muted-foreground">
                  Found in the sheet URL: docs.google.com/spreadsheets/d/<b>ID</b>/edit
                </p>
              </div>
              <Button
                className="mt-4 w-full rounded-full"
                disabled={busy || !sheetId.trim()}
                data-testid="sheets-connect-btn"
                onClick={connect}
              >
                Connect
              </Button>
              {!state.credentials_configured && (
                <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2.5 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                  A Google service account is required. Paste its JSON into
                  <span className="font-mono-plex"> GOOGLE_SERVICE_ACCOUNT_JSON</span> in
                  <span className="font-mono-plex"> backend/.env</span>, share the sheet with the service account email,
                  then connect. Until then every order still saves normally and sync jobs simply stay
                  <b> pending</b>.
                </p>
              )}
            </div>

            <div className="card-surface p-6">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Tabs created</p>
              <ul className="mt-3 space-y-1.5 text-sm">
                {state.tabs.map((tab) => (
                  <li key={tab} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full bg-primary" /> {tab}
                  </li>
                ))}
              </ul>
              <p className="mt-4 text-xs text-muted-foreground">
                Sheets sync runs in the background and can never delay or fail an order.
              </p>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
