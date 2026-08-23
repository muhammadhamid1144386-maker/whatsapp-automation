import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Ban, KeyRound, ShieldCheck, Trash2, Wallet } from "lucide-react";
import { toast } from "sonner";
import { AdminLayout } from "@/components/AdminLayout";
import { CredentialBox } from "@/pages/AdminClients";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { api, errText, money } from "@/lib/api";
import { PERIODS, SEVERITY, SubStatusBadge, dateOnly, dueLabel } from "@/lib/adminMeta";

export default function AdminClientDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [client, setClient] = useState(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState({ amount: "", billing_period: "monthly", grace_days: "7" });
  const [payOpen, setPayOpen] = useState(false);
  const [payment, setPayment] = useState({ amount: "", method: "Cash", note: "" });
  const [deleteOpen, setDeleteOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get(`/admin/clients/${id}`);
      setClient(data);
      setPlan({
        amount: String(data.subscription.amount ?? ""),
        billing_period: data.subscription.billing_period || "monthly",
        grace_days: String(data.subscription.grace_days ?? 7),
      });
      setPayment((p) => ({ ...p, amount: String(data.subscription.amount ?? "") }));
    } catch (e) {
      toast.error(errText(e));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (path, message, body) => {
    setBusy(true);
    try {
      await api.post(`/admin/clients/${id}/${path}`, body ?? {});
      toast.success(message);
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const savePlan = async () => {
    setBusy(true);
    try {
      await api.put(`/admin/clients/${id}/subscription`, {
        amount: Number(plan.amount) || 0,
        billing_period: plan.billing_period,
        grace_days: Number(plan.grace_days) || 0,
      });
      toast.success("Plan updated");
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const takePayment = async () => {
    if (!Number(payment.amount)) {
      toast.error("Enter the amount received");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post(`/admin/clients/${id}/payment`, {
        amount: Number(payment.amount),
        method: payment.method,
        note: payment.note,
      });
      toast.success("Payment recorded", { description: `Active until ${dateOnly(data.current_period_end)}` });
      setPayOpen(false);
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    setBusy(true);
    try {
      const { data } = await api.post(`/admin/clients/${id}/regenerate-password`);
      toast.success("New password generated", { description: data.password });
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    try {
      await api.delete(`/admin/clients/${id}`);
      toast.success("Client removed");
      navigate("/admin/clients");
    } catch (e) {
      toast.error(errText(e));
    }
  };

  if (!client) {
    return (
      <AdminLayout title="Client">
        <div className="grid gap-6 lg:grid-cols-3">
          <Skeleton className="h-96 rounded-xl lg:col-span-2" />
          <Skeleton className="h-96 rounded-xl" />
        </div>
      </AdminLayout>
    );
  }

  const sub = client.subscription;
  const blocked = sub.status === "blocked";

  return (
    <AdminLayout
      title={client.name}
      subtitle={`${client.city || "—"} · joined ${dateOnly(client.created_at)}`}
      actions={
        <Link to="/admin/clients">
          <Button variant="outline" size="sm" className="shrink-0 rounded-full" data-testid="admin-client-back">
            <ArrowLeft className="mr-1.5 h-3.5 w-3.5" /> Clients
          </Button>
        </Link>
      }
    >
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="card-surface p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Subscription</p>
                <p className="mt-2 font-display text-2xl font-bold tabular-nums">
                  {money(sub.amount)}
                  <span className="ml-1 text-sm font-medium text-muted-foreground">/ {sub.billing_period}</span>
                </p>
                <p className="mt-1 text-sm text-muted-foreground" data-testid="admin-client-due">
                  Renews {dateOnly(sub.current_period_end)} · {dueLabel(sub)}
                </p>
                {sub.status === "grace" && (
                  <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                    Auto-block on {dateOnly(sub.grace_ends_at)} if payment is not received
                  </p>
                )}
              </div>
              <SubStatusBadge status={sub.status} testId="admin-client-sub-status" />
            </div>

            <div className="mt-6 flex flex-wrap gap-2">
              <Button className="rounded-full" disabled={busy} data-testid="admin-record-payment-btn" onClick={() => setPayOpen(true)}>
                <Wallet className="mr-1.5 h-4 w-4" /> Mark as paid
              </Button>
              {blocked ? (
                <Button variant="outline" className="rounded-full" disabled={busy} data-testid="admin-unblock-btn" onClick={() => act("unblock", "Client reactivated")}>
                  <ShieldCheck className="mr-1.5 h-4 w-4" /> Unblock
                </Button>
              ) : (
                <Button variant="outline" className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10" disabled={busy} data-testid="admin-block-btn" onClick={() => act("block", "Client blocked")}>
                  <Ban className="mr-1.5 h-4 w-4" /> Block access
                </Button>
              )}
              <Button variant="outline" className="rounded-full" disabled={busy} data-testid="admin-regenerate-btn" onClick={regenerate}>
                <KeyRound className="mr-1.5 h-4 w-4" /> New password
              </Button>
              {!client.demo && (
                <Button variant="ghost" className="rounded-full text-destructive" data-testid="admin-delete-btn" onClick={() => setDeleteOpen(true)}>
                  <Trash2 className="mr-1.5 h-4 w-4" /> Delete
                </Button>
              )}
            </div>

            <div className="mt-6 grid gap-4 border-t pt-5 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label>Fee (PKR)</Label>
                <Input data-testid="admin-plan-amount" type="number" value={plan.amount} onChange={(e) => setPlan({ ...plan, amount: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Billing period</Label>
                <Select value={plan.billing_period} onValueChange={(v) => setPlan({ ...plan, billing_period: v })}>
                  <SelectTrigger data-testid="admin-plan-period">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-popover">
                    {PERIODS.map((p) => (
                      <SelectItem key={p.value} value={p.value} data-testid={`admin-plan-period-${p.value}`}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Grace days</Label>
                <Input data-testid="admin-plan-grace" type="number" value={plan.grace_days} onChange={(e) => setPlan({ ...plan, grace_days: e.target.value })} />
              </div>
            </div>
            <Button variant="outline" size="sm" className="mt-4 rounded-full" disabled={busy} data-testid="admin-plan-save" onClick={savePlan}>
              Save plan
            </Button>
          </div>

          <div className="card-surface overflow-hidden">
            <div className="border-b px-6 py-4">
              <h2 className="font-display text-lg font-bold">Payment history</h2>
            </div>
            {client.payments.length === 0 ? (
              <p className="px-6 py-10 text-center text-sm text-muted-foreground">
                No payments recorded yet. Total collected: {money(sub.total_collected)}
              </p>
            ) : (
              <table className="w-full text-sm" data-testid="admin-payments-table">
                <thead>
                  <tr className="border-b text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-6 py-3 text-left font-semibold">Date</th>
                    <th className="px-6 py-3 text-right font-semibold">Amount</th>
                    <th className="px-6 py-3 text-left font-semibold">Method</th>
                    <th className="px-6 py-3 text-left font-semibold">Covers until</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {client.payments.map((p) => (
                    <tr key={p.id}>
                      <td className="px-6 py-3">{dateOnly(p.created_at)}</td>
                      <td className="px-6 py-3 text-right tabular-nums font-medium">{money(p.amount)}</td>
                      <td className="px-6 py-3">{p.method}</td>
                      <td className="px-6 py-3">{dateOnly(p.period_end)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="card-surface p-6">
            <CredentialBox email={client.credentials?.email} password={client.credentials?.password} testIdPrefix="admin-client-cred" />
            {blocked && (
              <p className="mt-3 rounded-lg bg-destructive/10 px-3 py-2 text-xs text-destructive">
                This login is currently refused because the client is blocked.
              </p>
            )}
          </div>

          <div className="card-surface p-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Usage</p>
            <dl className="mt-3 space-y-2 text-sm">
              {[
                ["Orders", client.usage.orders],
                ["Order value", money(client.usage.gmv)],
                ["Customers", client.usage.customers],
                ["Menu items", client.usage.menu_items],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between">
                  <dt className="text-muted-foreground">{label}</dt>
                  <dd className="font-medium tabular-nums">{value}</dd>
                </div>
              ))}
            </dl>
          </div>

          <div className="card-surface p-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Activity</p>
            <div className="mt-3 space-y-2" data-testid="admin-client-alerts">
              {client.alerts.length === 0 && <p className="text-sm text-muted-foreground">Nothing logged yet.</p>}
              {client.alerts.map((a) => (
                <div key={a.id} className={`rounded-lg border border-l-4 bg-muted/40 px-3 py-2 ${SEVERITY[a.severity] || SEVERITY.info}`}>
                  <p className="text-xs">{a.message}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">{dateOnly(a.created_at)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <Dialog open={payOpen} onOpenChange={setPayOpen}>
        <DialogContent className="bg-card">
          <DialogHeader>
            <DialogTitle className="font-display">Record payment</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Amount received (PKR)</Label>
              <Input data-testid="payment-amount-input" type="number" value={payment.amount} onChange={(e) => setPayment({ ...payment, amount: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <Label>Method</Label>
              <Select value={payment.method} onValueChange={(v) => setPayment({ ...payment, method: v })}>
                <SelectTrigger data-testid="payment-method-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-popover">
                  {["Cash", "Bank transfer", "JazzCash", "Easypaisa", "Other"].map((m) => (
                    <SelectItem key={m} value={m} data-testid={`payment-method-${m.toLowerCase().replace(/\s+/g, "-")}`}>
                      {m}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Note</Label>
              <Input data-testid="payment-note-input" value={payment.note} onChange={(e) => setPayment({ ...payment, note: e.target.value })} placeholder="Reference number, etc." />
            </div>
            <p className="rounded-lg bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              Recording a payment reactivates the client, clears reminders and pushes the renewal date forward by one{" "}
              {sub.billing_period === "monthly" ? "month" : sub.billing_period === "quarterly" ? "quarter" : "year"}.
            </p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setPayOpen(false)} data-testid="payment-cancel-btn">
              Cancel
            </Button>
            <Button onClick={takePayment} disabled={busy} className="rounded-full" data-testid="payment-save-btn">
              Confirm payment
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent className="bg-card">
          <DialogHeader>
            <DialogTitle className="font-display">Delete {client.name}?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            This permanently removes their menu, orders, customers, conversations and login. It cannot be undone.
          </p>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteOpen(false)} data-testid="delete-cancel-btn">
              Keep client
            </Button>
            <Button variant="destructive" onClick={remove} data-testid="delete-confirm-btn">
              Delete permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminLayout>
  );
}
