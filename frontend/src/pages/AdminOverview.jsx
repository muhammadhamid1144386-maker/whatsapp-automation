import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, Ban, CheckCircle2, PlayCircle, TrendingUp, Users, Wallet } from "lucide-react";
import { toast } from "sonner";
import { AdminLayout } from "@/components/AdminLayout";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errText, money } from "@/lib/api";
import { SubStatusBadge, dateOnly, dueLabel } from "@/lib/adminMeta";

const Stat = ({ label, value, hint, icon: Icon, testId, accent }) => (
  <div data-testid={testId} className="card-surface p-6">
    <div className="flex items-start justify-between">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{label}</p>
      <span className={`grid h-8 w-8 place-items-center rounded-lg ${accent || "bg-primary/10 text-primary"}`}>
        <Icon className="h-4 w-4" />
      </span>
    </div>
    <p className="mt-4 font-display text-3xl font-bold tabular-nums">{value}</p>
    {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
  </div>
);

export default function AdminOverview() {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get("/admin/overview");
      setData(res.data);
    } catch (e) {
      toast.error(errText(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runCheck = async () => {
    setBusy(true);
    try {
      const { data: result } = await api.post("/admin/subscriptions/run-check");
      toast.success("Subscription check complete", {
        description: `${result.checked} checked · ${result.reminded} reminders · ${result.moved_to_grace} in grace · ${result.blocked} blocked`,
      });
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AdminLayout
      title="Platform overview"
      subtitle="Your clients, their subscriptions and what needs chasing"
      actions={
        <Button size="sm" className="shrink-0 rounded-full" disabled={busy} data-testid="admin-run-check-btn" onClick={runCheck}>
          <PlayCircle className="mr-1.5 h-4 w-4" /> Run check
        </Button>
      }
    >
      {!data ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <Stat testId="admin-stat-clients" label="Total clients" value={data.total_clients} icon={Users} hint={`${data.active_clients} active`} />
            <Stat testId="admin-stat-mrr" label="Monthly recurring" value={money(data.monthly_recurring)} icon={TrendingUp} hint="Across active clients" accent="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" />
            <Stat testId="admin-stat-collected" label="Collected" value={money(data.collected_total)} icon={Wallet} hint={`${data.payments_recorded} payments`} />
            <Stat testId="admin-stat-outstanding" label="Outstanding" value={money(data.outstanding)} icon={AlertTriangle} hint={`${data.grace_clients} in grace`} accent="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300" />
            <Stat testId="admin-stat-blocked" label="Blocked" value={data.blocked_clients} icon={Ban} hint="Login refused" accent="bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300" />
          </div>

          <div className="card-surface mt-6 overflow-hidden">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <div>
                <h2 className="font-display text-lg font-bold">Needs chasing</h2>
                <p className="text-xs text-muted-foreground">Expiring within 7 days, overdue, or already blocked</p>
              </div>
              <Link to="/admin/clients" className="text-sm font-medium text-primary hover:underline" data-testid="admin-all-clients-link">
                All clients
              </Link>
            </div>
            {data.expiring_soon.length === 0 ? (
              <div className="flex flex-col items-center px-6 py-12 text-center">
                <CheckCircle2 className="h-8 w-8 text-emerald-600" />
                <p className="mt-3 text-sm text-muted-foreground">
                  Everyone is paid up. Nothing to chase right now.
                </p>
              </div>
            ) : (
              <div className="divide-y" data-testid="admin-expiring-list">
                {data.expiring_soon.map((client) => (
                  <Link
                    key={client.id}
                    to={`/admin/clients/${client.id}`}
                    data-testid={`admin-expiring-${client.slug}`}
                    className="flex flex-wrap items-center gap-4 px-6 py-4 transition-colors hover:bg-accent/50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">{client.name}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {client.owner_email} · renews {dateOnly(client.subscription.current_period_end)}
                      </p>
                    </div>
                    <span className="text-sm font-semibold tabular-nums">{money(client.subscription.amount)}</span>
                    <span className="text-xs font-medium text-muted-foreground">{dueLabel(client.subscription)}</span>
                    <SubStatusBadge status={client.subscription.status} />
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                  </Link>
                ))}
              </div>
            )}
          </div>

          <div className="card-surface mt-6 overflow-hidden">
            <div className="border-b px-6 py-4">
              <h2 className="font-display text-lg font-bold">Newest clients</h2>
            </div>
            <div className="divide-y">
              {data.recent_clients.length === 0 && (
                <p className="px-6 py-10 text-center text-sm text-muted-foreground">
                  No clients yet — add your first one from the Clients page.
                </p>
              )}
              {data.recent_clients.map((client) => (
                <Link
                  key={client.id}
                  to={`/admin/clients/${client.id}`}
                  className="flex flex-wrap items-center gap-4 px-6 py-4 transition-colors hover:bg-accent/50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-semibold">{client.name}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {client.city || "—"} · joined {dateOnly(client.created_at)} · {client.orders} orders
                    </p>
                  </div>
                  <SubStatusBadge status={client.subscription.status} />
                </Link>
              ))}
            </div>
          </div>
        </>
      )}
    </AdminLayout>
  );
}
