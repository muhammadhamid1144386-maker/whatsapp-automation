import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ArrowLeft, Bike, MessageSquare, RefreshCw, ShoppingBag } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api, clockTime, errText, money } from "@/lib/api";
import { NEXT_ACTIONS, STATUS_META } from "@/lib/orderMeta";
import { useDashboardStream } from "@/hooks/useRealtime";

export default function OrderDetail() {
  const { id } = useParams();
  const [payload, setPayload] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/orders/${id}`);
      setPayload(data);
    } catch (e) {
      toast.error(errText(e));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useDashboardStream((event) => {
    if (event.startsWith("ORDER_")) load();
  });

  const order = payload?.order;

  const advance = async (status, reason) => {
    setBusy(true);
    try {
      await api.post(`/orders/${id}/status`, { status, reason });
      toast.success(`Moved to ${status.replace(/_/g, " ").toLowerCase()}`);
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const resync = async () => {
    try {
      const result = await api.post(`/orders/${id}/resync`);
      toast.info(`Sync attempted: ${result.data.synced} synced, ${result.data.failed} failed`);
      load();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  return (
    <DashboardLayout
      title={order ? order.order_number : "Order"}
      subtitle={order ? `${order.customer_name} · ${order.order_type}` : "Loading"}
      actions={
        <Link to="/orders">
          <Button variant="outline" size="sm" className="rounded-full" data-testid="order-back-btn">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> Board
          </Button>
        </Link>
      }
    >
      {!order ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-80 rounded-xl lg:col-span-2" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div className="card-surface p-6">
              <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                  <p className="font-display text-2xl font-bold">{order.order_number}</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Placed {clockTime(order.created_at)} · updated {clockTime(order.updated_at)}
                  </p>
                </div>
                <StatusBadge status={order.status} testId="detail-status-badge" />
              </div>

              <div className="mt-6 grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg bg-muted/50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Customer</p>
                  <p className="mt-1 font-medium" data-testid="detail-customer-name">{order.customer_name}</p>
                  <p className="text-sm text-muted-foreground">{order.customer_phone}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {payload.customer_order_count} order{payload.customer_order_count === 1 ? "" : "s"} with you
                  </p>
                </div>
                <div className="rounded-lg bg-muted/50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Fulfilment</p>
                  <p className="mt-1 flex items-center gap-1.5 font-medium capitalize">
                    {order.order_type === "delivery" ? <Bike className="h-4 w-4" /> : <ShoppingBag className="h-4 w-4" />}
                    {order.order_type}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    ETA {order.eta_min}–{order.eta_max} minutes
                  </p>
                  {order.address && <p className="mt-1 text-xs text-muted-foreground">{order.address}</p>}
                </div>
              </div>

              <table className="mt-6 w-full text-sm">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="pb-2 text-left font-semibold">Item</th>
                    <th className="pb-2 text-right font-semibold">Unit</th>
                    <th className="pb-2 text-right font-semibold">Qty</th>
                    <th className="pb-2 text-right font-semibold">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {order.items.map((item, i) => (
                    <tr key={`${item.item_id}-${i}`} data-testid={`detail-item-${i}`}>
                      <td className="py-2.5">{item.name}</td>
                      <td className="py-2.5 text-right tabular-nums text-muted-foreground">{money(item.unit_price)}</td>
                      <td className="py-2.5 text-right tabular-nums">{item.quantity}</td>
                      <td className="py-2.5 text-right tabular-nums font-medium">{money(item.line_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="mt-4 space-y-1.5 border-t pt-4 text-sm">
                <div className="flex justify-between text-muted-foreground">
                  <span>Subtotal</span>
                  <span className="tabular-nums">{money(order.subtotal)}</span>
                </div>
                <div className="flex justify-between text-muted-foreground">
                  <span>Delivery fee</span>
                  <span className="tabular-nums">{money(order.delivery_fee)}</span>
                </div>
                {order.discount > 0 && (
                  <div className="flex justify-between text-muted-foreground">
                    <span>Discount</span>
                    <span className="tabular-nums">-{money(order.discount)}</span>
                  </div>
                )}
                <div className="flex justify-between font-display text-lg font-bold">
                  <span>Total</span>
                  <span data-testid="detail-total" className="tabular-nums">{money(order.total)}</span>
                </div>
                <p className="pt-1 text-xs text-muted-foreground">Payment: {order.payment_method}</p>
              </div>

              {order.reject_reason && (
                <p className="mt-4 rounded-lg bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  Reason: {order.reject_reason}
                </p>
              )}

              {(NEXT_ACTIONS[order.status] || []).length > 0 && (
                <div className="mt-6 flex flex-wrap gap-2 border-t pt-5">
                  {(NEXT_ACTIONS[order.status] || [])
                    .filter((a) =>
                      a.deliveryOnly ? order.order_type === "delivery" : a.pickupOnly ? order.order_type === "pickup" : true,
                    )
                    .map((action) => (
                      <Button
                        key={action.status}
                        size="sm"
                        disabled={busy}
                        variant={action.tone === "danger" ? "destructive" : "default"}
                        data-testid={`detail-action-${action.status}`}
                        className="rounded-full"
                        onClick={() => advance(action.status, action.tone === "danger" ? "Other" : undefined)}
                      >
                        {action.label}
                      </Button>
                    ))}
                  {order.status !== "CANCELLED" && !["DELIVERED", "REJECTED"].includes(order.status) && (
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      data-testid="detail-action-CANCELLED"
                      className="rounded-full"
                      onClick={() => advance("CANCELLED", "Other")}
                    >
                      Cancel order
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="card-surface p-6">
              <h3 className="font-display text-base font-bold">Status timeline</h3>
              <ol className="mt-4 space-y-4">
                {payload.history.map((entry) => (
                  <li key={entry.id} className="flex gap-3" data-testid={`timeline-${entry.new_status}`}>
                    <div className="flex flex-col items-center">
                      <span className="mt-1 h-2.5 w-2.5 rounded-full bg-primary" />
                      <span className="w-px flex-1 bg-border" />
                    </div>
                    <div className="pb-1">
                      <p className="text-sm font-medium">{STATUS_META[entry.new_status]?.label || entry.new_status}</p>
                      <p className="text-xs text-muted-foreground">
                        {clockTime(entry.created_at)} · {entry.changed_by}
                      </p>
                      {entry.note && <p className="text-xs text-muted-foreground">{entry.note}</p>}
                    </div>
                  </li>
                ))}
              </ol>
            </div>

            <div className="card-surface p-6">
              <h3 className="font-display text-base font-bold">Google Sheets sync</h3>
              <p className="mt-2 text-sm capitalize" data-testid="detail-sync-status">
                Order sync status: <span className="font-semibold">{order.google_sync_status}</span>
              </p>
              <ul className="mt-3 space-y-2 text-xs text-muted-foreground">
                {payload.sync_jobs.length === 0 && <li>No sync jobs queued.</li>}
                {payload.sync_jobs.map((job, i) => (
                  <li key={i} className="rounded-lg bg-muted/50 px-3 py-2">
                    <span className="font-medium">{job.event}</span> · {job.sync_status} ({job.sync_attempts} attempts)
                    {job.error_message && <p className="mt-1 text-destructive">{job.error_message}</p>}
                  </li>
                ))}
              </ul>
              <Button variant="outline" size="sm" className="mt-4 w-full rounded-full" data-testid="detail-resync-btn" onClick={resync}>
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Retry sync
              </Button>
            </div>

            {payload.conversation_id && (
              <Link to={`/conversations?id=${payload.conversation_id}`}>
                <Button variant="outline" className="w-full rounded-full" data-testid="detail-conversation-btn">
                  <MessageSquare className="mr-2 h-4 w-4" /> Open conversation
                </Button>
              </Link>
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
