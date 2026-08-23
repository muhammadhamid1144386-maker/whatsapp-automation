import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, Bike, Clock, IndianRupee, Receipt, RefreshCw, Sheet, ShoppingBag, Smartphone, TrendingUp, Users,
} from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errText, money, timeAgo } from "@/lib/api";
import { useDashboardStream } from "@/hooks/useRealtime";

const Stat = ({ label, value, hint, icon: Icon, testId, accent }) => (
  <div data-testid={testId} className="card-surface relative overflow-hidden p-6">
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

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const [{ data: s }, { data: o }] = await Promise.all([
        api.get("/analytics/summary"),
        api.get("/orders", { params: { limit: 8 } }),
      ]);
      setSummary(s);
      setOrders(o);
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useDashboardStream((event) => {
    if (event.startsWith("NEW_ORDER") || event.startsWith("ORDER_")) load();
  });

  return (
    <DashboardLayout
      title="Dashboard"
      subtitle="Live snapshot of today's business"
      actions={
        <Button variant="outline" size="sm" className="rounded-full" data-testid="dashboard-refresh-btn" onClick={load}>
          <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Refresh
        </Button>
      }
    >
      {loading ? (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
          {[...Array(8)].map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-xl" />
          ))}
        </div>
      ) : (
        <>
          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            <Stat testId="stat-today-orders" label="Today's orders" value={summary.today_orders} icon={Receipt} hint={`${summary.lifetime_orders} lifetime`} />
            <Stat testId="stat-today-sales" label="Today's sales" value={money(summary.today_sales)} icon={TrendingUp} hint={`${money(summary.week_sales)} this week`} accent="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" />
            <Stat testId="stat-pending-orders" label="Pending" value={summary.pending_orders} icon={Clock} hint="Awaiting kitchen action" accent="bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300" />
            <Stat testId="stat-completed-orders" label="Completed today" value={summary.completed_orders} icon={ShoppingBag} accent="bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300" />
            <Stat testId="stat-avg-order" label="Average order" value={money(summary.average_order_value)} icon={IndianRupee} hint={`${summary.total_customers} customers`} />
          </div>

          <div className="mt-6 grid gap-5 lg:grid-cols-3">
            <div className="card-surface p-6">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">WhatsApp channel</p>
                <Smartphone className="h-4 w-4 text-muted-foreground" />
              </div>
              <p className="mt-3 flex items-center gap-2 font-display text-xl font-bold capitalize">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    summary.whatsapp.status === "connected" ? "bg-emerald-500 anim-pulse-ring" : "bg-stone-400"
                  }`}
                />
                <span data-testid="dashboard-whatsapp-status">{summary.whatsapp.status || "disconnected"}</span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">{summary.whatsapp.connected_number || "No number paired"}</p>
              <Link to="/whatsapp" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline" data-testid="dashboard-whatsapp-link">
                Manage channel <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="card-surface p-6">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Google Sheets sync</p>
                <Sheet className="h-4 w-4 text-muted-foreground" />
              </div>
              <p className="mt-3 font-display text-xl font-bold capitalize" data-testid="dashboard-sheets-status">
                {summary.google_sheets.status === "connected" ? "Connected" : "Not connected"}
              </p>
              <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                <span data-testid="dashboard-sync-pending">{summary.google_sheets.pending} pending</span>
                <span>{summary.google_sheets.synced} synced</span>
                <span>{summary.google_sheets.failed} failed</span>
              </div>
              <Link to="/google-sheets" className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-primary hover:underline" data-testid="dashboard-sheets-link">
                Open sync centre <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="card-surface p-6">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Top items</p>
                <Users className="h-4 w-4 text-muted-foreground" />
              </div>
              {summary.top_items.length === 0 ? (
                <p className="mt-3 text-sm text-muted-foreground">No orders yet.</p>
              ) : (
                <ul className="mt-3 space-y-2 text-sm">
                  {summary.top_items.slice(0, 4).map((item) => (
                    <li key={item.name} className="flex items-center justify-between gap-2">
                      <span className="truncate">{item.name}</span>
                      <span className="font-mono-plex text-xs text-muted-foreground">{item.quantity}×</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          <div className="card-surface mt-6 overflow-hidden">
            <div className="flex items-center justify-between border-b px-6 py-4">
              <h2 className="font-display text-lg font-bold">Recent orders</h2>
              <Link to="/orders" className="text-sm font-medium text-primary hover:underline" data-testid="dashboard-all-orders-link">
                View live board
              </Link>
            </div>
            {orders.length === 0 ? (
              <div className="px-6 py-12 text-center">
                <p className="text-sm text-muted-foreground">
                  No orders yet. Open the WhatsApp simulator and place one to see it arrive here live.
                </p>
                <Link to="/whatsapp">
                  <Button className="mt-4 rounded-full" data-testid="dashboard-empty-simulator-btn">
                    Open WhatsApp simulator
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="divide-y">
                {orders.map((order) => (
                  <Link
                    key={order.id}
                    to={`/orders/${order.id}`}
                    data-testid={`recent-order-${order.order_number}`}
                    className="flex items-center gap-4 px-6 py-4 transition-colors hover:bg-accent/50"
                  >
                    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-muted">
                      {order.order_type === "delivery" ? <Bike className="h-4 w-4" /> : <ShoppingBag className="h-4 w-4" />}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold">
                        {order.order_number} · {order.customer_name}
                      </p>
                      <p className="truncate text-xs text-muted-foreground">
                        {(order.items || []).map((i) => `${i.quantity}× ${i.name}`).join(", ")}
                      </p>
                    </div>
                    <div className="hidden text-right sm:block">
                      <p className="text-sm font-semibold tabular-nums">{money(order.total)}</p>
                      <p className="text-xs text-muted-foreground">{timeAgo(order.created_at)}</p>
                    </div>
                    <StatusBadge status={order.status} />
                  </Link>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </DashboardLayout>
  );
}
