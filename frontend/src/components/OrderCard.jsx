import { useState } from "react";
import { Link } from "react-router-dom";
import { Bike, Clock, MapPin, Phone, ShoppingBag, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { StatusBadge } from "@/components/StatusBadge";
import { NEXT_ACTIONS } from "@/lib/orderMeta";
import { api, errText, money, timeAgo } from "@/lib/api";

const REJECT_REASONS = ["Item unavailable", "Restaurant closed", "Delivery unavailable", "Other"];

export const OrderCard = ({ order, onChanged, fresh = false }) => {
  const [busy, setBusy] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [reason, setReason] = useState(REJECT_REASONS[0]);

  const actions = (NEXT_ACTIONS[order.status] || []).filter((a) => {
    if (a.deliveryOnly) return order.order_type === "delivery";
    if (a.pickupOnly) return order.order_type === "pickup";
    return true;
  });

  const setStatus = async (status, rejectReason) => {
    setBusy(true);
    try {
      const { data } = await api.post(`/orders/${order.id}/status`, { status, reason: rejectReason });
      toast.success(`${order.order_number} → ${status.replace(/_/g, " ").toLowerCase()}`, {
        description: data.notified ? "WhatsApp notification sent to the customer" : undefined,
      });
      onChanged?.();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
      setRejectOpen(false);
    }
  };

  const minutesOld = Math.floor((Date.now() - new Date(`${(order.created_at || "").replace(" ", "T")}`).getTime()) / 60000);
  const stale = order.status === "NEW" && minutesOld > 15;

  return (
    <div
      data-testid={`order-card-${order.order_number}`}
      className={`card-surface p-5 ${fresh ? "anim-slide-in ring-2 ring-primary/40" : ""}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/orders/${order.id}`}
            data-testid={`order-link-${order.order_number}`}
            className="font-display text-lg font-bold tracking-tight hover:text-primary transition-colors"
          >
            {order.order_number}
          </Link>
          <p className="truncate text-sm font-medium">{order.customer_name}</p>
          <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Phone className="h-3 w-3" /> {order.customer_phone}
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <StatusBadge status={order.status} testId={`order-status-${order.order_number}`} />
          <span className={`text-xs font-semibold ${stale ? "text-destructive" : "text-muted-foreground"}`}>
            {timeAgo(order.created_at)}
          </span>
        </div>
      </div>

      <ul className="mt-4 space-y-1 text-sm">
        {(order.items || []).map((item, i) => (
          <li key={`${item.item_id}-${i}`} className="flex justify-between gap-3">
            <span className="truncate">
              <span className="font-mono-plex text-xs text-primary">{item.quantity}×</span> {item.name}
            </span>
            <span className="tabular-nums text-muted-foreground">{money(item.line_total)}</span>
          </li>
        ))}
      </ul>

      <div className="mt-4 space-y-1 border-t pt-3 text-sm">
        <div className="flex justify-between text-muted-foreground">
          <span>Subtotal</span>
          <span className="tabular-nums">{money(order.subtotal)}</span>
        </div>
        {order.delivery_fee > 0 && (
          <div className="flex justify-between text-muted-foreground">
            <span>Delivery</span>
            <span className="tabular-nums">{money(order.delivery_fee)}</span>
          </div>
        )}
        <div className="flex justify-between font-display text-base font-bold">
          <span>Total</span>
          <span data-testid={`order-total-${order.order_number}`} className="tabular-nums">{money(order.total)}</span>
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span className="inline-flex items-center gap-1 font-medium capitalize">
          {order.order_type === "delivery" ? <Bike className="h-3.5 w-3.5" /> : <ShoppingBag className="h-3.5 w-3.5" />}
          {order.order_type}
        </span>
        <span className="inline-flex items-center gap-1">
          <Clock className="h-3.5 w-3.5" /> {order.eta_min}–{order.eta_max} min
        </span>
      </div>
      {order.address && (
        <p className="mt-2 flex items-start gap-1.5 text-xs text-muted-foreground">
          <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {order.address}
        </p>
      )}

      {actions.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {actions.map((action) =>
            action.status === "REJECTED" ? (
              <Button
                key={action.status}
                data-testid={`order-reject-${order.order_number}`}
                variant="outline"
                size="sm"
                disabled={busy}
                onClick={() => setRejectOpen(true)}
                className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10"
              >
                Reject
              </Button>
            ) : (
              <Button
                key={action.status}
                data-testid={`order-advance-${order.order_number}`}
                size="sm"
                disabled={busy}
                onClick={() => setStatus(action.status)}
                className="rounded-full"
              >
                {action.label} <ChevronRight className="ml-0.5 h-3.5 w-3.5" />
              </Button>
            ),
          )}
        </div>
      )}

      <Dialog open={rejectOpen} onOpenChange={setRejectOpen}>
        <DialogContent className="bg-card">
          <DialogHeader>
            <DialogTitle className="font-display">Reject {order.order_number}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            The customer is told immediately on WhatsApp, with the reason you pick.
          </p>
          <div className="space-y-2">
            {REJECT_REASONS.map((r) => (
              <button
                key={r}
                type="button"
                data-testid={`reject-reason-${r.toLowerCase().replace(/\s+/g, "-")}`}
                onClick={() => setReason(r)}
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                  reason === r ? "border-primary bg-primary/10 font-medium" : "hover:bg-accent"
                }`}
              >
                {r}
              </button>
            ))}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRejectOpen(false)} data-testid="reject-cancel-btn">
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              data-testid="reject-confirm-btn"
              onClick={() => setStatus("REJECTED", reason)}
            >
              Reject order
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
