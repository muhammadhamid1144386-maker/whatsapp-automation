import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Link2, Plug, QrCode, RefreshCw, Smartphone, Unplug } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { WhatsAppSimulator } from "@/components/WhatsAppSimulator";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, clockTime, errText } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { useDashboardStream } from "@/hooks/useRealtime";

const STATUS_STYLE = {
  connected: "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-200",
  connecting: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-900/40 dark:text-amber-200",
  disconnected: "bg-stone-200 text-stone-700 border-stone-300 dark:bg-stone-800 dark:text-stone-200",
};

export default function WhatsAppPage() {
  const { user } = useAuth();
  const slug = user?.restaurant?.slug || "pizza-palace";
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState(false);
  const [phone, setPhone] = useState("03001234567");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/whatsapp/status");
      setState(data);
    } catch (e) {
      toast.error(errText(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useDashboardStream((event) => {
    if (event === "WHATSAPP_STATUS" || event === "WHATSAPP_LOG") load();
  });

  const act = async (path, message) => {
    setBusy(true);
    try {
      await api.post(`/whatsapp/${path}`);
      toast.success(message);
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const status = state?.session?.status || "disconnected";

  return (
    <DashboardLayout title="WhatsApp" subtitle="Channel connection, pairing and live simulator">
      {!state ? (
        <Skeleton className="h-96 rounded-xl" />
      ) : (
        <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
          <div className="space-y-6">
            <div className="card-surface p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Connection status
                  </p>
                  <p className="mt-2 flex items-center gap-2 font-display text-2xl font-bold capitalize">
                    <span
                      className={`h-3 w-3 rounded-full ${
                        status === "connected" ? "bg-emerald-500 anim-pulse-ring" : status === "connecting" ? "bg-amber-500" : "bg-stone-400"
                      }`}
                    />
                    <span data-testid="whatsapp-status-text">{status}</span>
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {state.session.connected_number || "No number paired"} · provider{" "}
                    <span className="font-mono-plex">{state.provider}</span>
                  </p>
                  {state.session.last_connected_at && (
                    <p className="text-xs text-muted-foreground">
                      Last connected {clockTime(state.session.last_connected_at)}
                    </p>
                  )}
                </div>
                <span className={`rounded-full border px-3 py-1 text-xs font-semibold capitalize ${STATUS_STYLE[status]}`}>
                  {status}
                </span>
              </div>

              <div className="mt-6 flex flex-wrap gap-2">
                <Button
                  className="rounded-full"
                  disabled={busy}
                  data-testid="whatsapp-connect-btn"
                  onClick={() => act("connect", "WhatsApp channel connected")}
                >
                  <Plug className="mr-1.5 h-4 w-4" /> {status === "connected" ? "Reconnect" : "Connect"}
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full"
                  disabled={busy}
                  data-testid="whatsapp-qr-btn"
                  onClick={() => act("qr", "Pairing code generated")}
                >
                  <QrCode className="mr-1.5 h-4 w-4" /> Generate QR
                </Button>
                <Button
                  variant="outline"
                  className="rounded-full"
                  disabled={busy || status === "disconnected"}
                  data-testid="whatsapp-disconnect-btn"
                  onClick={() => act("disconnect", "Channel disconnected")}
                >
                  <Unplug className="mr-1.5 h-4 w-4" /> Disconnect
                </Button>
                <Button variant="ghost" className="rounded-full" data-testid="whatsapp-refresh-btn" onClick={load}>
                  <RefreshCw className="h-4 w-4" />
                </Button>
              </div>

              {state.session.qr_payload && (
                <div className="mt-6 flex flex-col items-center gap-3 rounded-xl border border-dashed p-6">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Pairing payload
                  </p>
                  <div className="grid h-40 w-40 grid-cols-8 gap-0.5 rounded-lg bg-white p-2">
                    {[...Array(64)].map((_, i) => (
                      <span
                        key={i}
                        className={`rounded-[1px] ${
                          (state.session.qr_payload.charCodeAt(i % state.session.qr_payload.length) + i) % 3 === 0
                            ? "bg-stone-900"
                            : "bg-transparent"
                        }`}
                      />
                    ))}
                  </div>
                  <p className="break-all font-mono-plex text-[10px] text-muted-foreground">
                    {state.session.qr_payload}
                  </p>
                  <p className="text-center text-xs text-muted-foreground">
                    Simulator pairing — press Connect to finish. With the Baileys provider this is a real scannable QR.
                  </p>
                </div>
              )}
            </div>

            <div className="card-surface p-6">
              <div className="flex items-start gap-3 rounded-lg bg-amber-50 p-4 text-xs text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                <p>{state.provider_note}</p>
              </div>
              <div className="mt-5">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Connection logs</p>
                <ul className="mt-3 space-y-1.5 text-xs" data-testid="whatsapp-logs">
                  {state.logs.length === 0 && <li className="text-muted-foreground">No activity yet.</li>}
                  {state.logs.map((log, i) => (
                    <li key={i} className="flex gap-3 rounded-lg bg-muted/50 px-3 py-2">
                      <span className="font-mono-plex text-muted-foreground">{clockTime(log.created_at)}</span>
                      <span className={log.level === "warn" ? "text-amber-600 dark:text-amber-400" : ""}>{log.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Smartphone className="h-4 w-4 text-muted-foreground" />
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Live simulator</p>
            </div>
            <div className="flex gap-2">
              <Input
                data-testid="simulator-phone-input"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Customer phone"
                className="h-9"
              />
              <Button variant="outline" size="sm" className="shrink-0 rounded-full" onClick={() => window.open("/chat", "_blank")} data-testid="open-public-chat-btn">
                <Link2 className="h-3.5 w-3.5" />
              </Button>
            </div>
            <WhatsAppSimulator slug={slug} phone={phone} />
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
