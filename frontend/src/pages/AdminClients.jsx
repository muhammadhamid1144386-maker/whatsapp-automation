import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Check, Copy, Eye, EyeOff, Plus, Search, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { AdminLayout } from "@/components/AdminLayout";
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
import { PERIODS, SubStatusBadge, dateOnly, dueLabel } from "@/lib/adminMeta";

const FILTERS = ["ALL", "active", "grace", "blocked"];
const emptyForm = {
  restaurant_name: "", owner_name: "", email: "", city: "", phone: "",
  whatsapp_number: "", amount: "5000", billing_period: "monthly",
};

export const CredentialBox = ({ email, password, testIdPrefix = "cred" }) => {
  const [show, setShow] = useState(false);
  const copy = (value, label) => {
    navigator.clipboard?.writeText(value);
    toast.success(`${label} copied`);
  };
  return (
    <div className="space-y-2 rounded-lg border bg-muted/40 p-4">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Login to hand over to the client
      </p>
      <div className="flex items-center gap-2">
        <span className="w-20 shrink-0 text-xs text-muted-foreground">Username</span>
        <code data-testid={`${testIdPrefix}-email`} className="min-w-0 flex-1 truncate font-mono-plex text-sm">
          {email || "—"}
        </code>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => copy(email, "Username")} data-testid={`${testIdPrefix}-copy-email`}>
          <Copy className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="flex items-center gap-2">
        <span className="w-20 shrink-0 text-xs text-muted-foreground">Password</span>
        <code data-testid={`${testIdPrefix}-password`} className="min-w-0 flex-1 truncate font-mono-plex text-sm">
          {password ? (show ? password : "••••••••••••") : "—"}
        </code>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setShow((s) => !s)} data-testid={`${testIdPrefix}-toggle`}>
          {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => copy(password, "Password")} data-testid={`${testIdPrefix}-copy-password`}>
          <Copy className="h-3.5 w-3.5" />
        </Button>
      </div>
      <p className="text-[11px] text-muted-foreground">
        This login is already assigned to their restaurant dashboard — they can sign in at /login straight away.
      </p>
    </div>
  );
};

export default function AdminClients() {
  const [clients, setClients] = useState(null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("ALL");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [busy, setBusy] = useState(false);
  const [created, setCreated] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/clients", {
        params: { search: search || undefined, status: filter },
      });
      setClients(data);
    } catch (e) {
      toast.error(errText(e));
    }
  }, [search, filter]);

  useEffect(() => {
    load();
  }, [load]);

  const submit = async () => {
    if (!form.restaurant_name.trim() || !form.owner_name.trim()) {
      toast.error("Restaurant name and owner name are required");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post("/admin/clients", {
        ...form,
        email: form.email.trim() || null,
        amount: Number(form.amount) || 0,
      });
      setCreated(data);
      setOpen(false);
      setForm(emptyForm);
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <AdminLayout
      title="Clients"
      subtitle="Onboard a restaurant, hand over its login, and track the subscription"
      actions={
        <Button size="sm" className="shrink-0 rounded-full" data-testid="admin-add-client-btn" onClick={() => setOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" /> Add client
        </Button>
      }
    >
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            data-testid="admin-clients-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search restaurant or city"
            className="pl-9"
          />
        </div>
        <div className="flex gap-1.5">
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              data-testid={`admin-filter-${f}`}
              onClick={() => setFilter(f)}
              className={`rounded-full border px-3 py-1.5 text-xs font-medium capitalize transition-colors ${
                filter === f ? "border-primary bg-primary/10 text-primary" : "hover:bg-accent"
              }`}
            >
              {f === "ALL" ? "All" : f}
            </button>
          ))}
        </div>
      </div>

      {!clients ? (
        <Skeleton className="h-80 rounded-xl" />
      ) : clients.length === 0 ? (
        <div className="card-surface flex flex-col items-center px-6 py-16 text-center">
          <UserPlus className="h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            No clients here yet. Add one and a login is generated automatically.
          </p>
          <Button className="mt-4 rounded-full" data-testid="admin-empty-add-btn" onClick={() => setOpen(true)}>
            Add your first client
          </Button>
        </div>
      ) : (
        <div className="card-surface overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm" data-testid="admin-clients-table">
            <thead>
              <tr className="border-b text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-6 py-3 text-left font-semibold">Restaurant</th>
                <th className="px-6 py-3 text-left font-semibold">Login</th>
                <th className="px-6 py-3 text-right font-semibold">Fee</th>
                <th className="px-6 py-3 text-left font-semibold">Renews</th>
                <th className="px-6 py-3 text-left font-semibold">Status</th>
                <th className="px-6 py-3 text-right font-semibold">Orders</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {clients.map((client) => (
                <tr key={client.id} data-testid={`admin-client-row-${client.slug}`} className="transition-colors hover:bg-accent/40">
                  <td className="px-6 py-3.5">
                    <Link to={`/admin/clients/${client.id}`} className="font-medium hover:text-primary" data-testid={`admin-client-link-${client.slug}`}>
                      {client.name}
                    </Link>
                    <p className="text-xs text-muted-foreground">{client.city || "—"}</p>
                  </td>
                  <td className="px-6 py-3.5 font-mono-plex text-xs text-muted-foreground">{client.owner_email}</td>
                  <td className="px-6 py-3.5 text-right tabular-nums">{money(client.subscription.amount)}</td>
                  <td className="px-6 py-3.5">
                    <p className="text-xs">{dateOnly(client.subscription.current_period_end)}</p>
                    <p className="text-[11px] text-muted-foreground">{dueLabel(client.subscription)}</p>
                  </td>
                  <td className="px-6 py-3.5">
                    <SubStatusBadge status={client.subscription.status} testId={`admin-client-status-${client.slug}`} />
                  </td>
                  <td className="px-6 py-3.5 text-right tabular-nums">{client.orders}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto bg-card">
          <DialogHeader>
            <DialogTitle className="font-display">New client</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Restaurant name *</Label>
                <Input data-testid="client-name-input" value={form.restaurant_name} onChange={(e) => setForm({ ...form, restaurant_name: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Owner name *</Label>
                <Input data-testid="client-owner-input" value={form.owner_name} onChange={(e) => setForm({ ...form, owner_name: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>City</Label>
                <Input data-testid="client-city-input" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Phone</Label>
                <Input data-testid="client-phone-input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>WhatsApp number</Label>
                <Input data-testid="client-whatsapp-input" value={form.whatsapp_number} onChange={(e) => setForm({ ...form, whatsapp_number: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Login email (optional)</Label>
                <Input data-testid="client-email-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="auto-generated" />
              </div>
              <div className="space-y-1.5">
                <Label>Fee (PKR)</Label>
                <Input data-testid="client-amount-input" type="number" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} />
              </div>
              <div className="space-y-1.5">
                <Label>Billing period</Label>
                <Select value={form.billing_period} onValueChange={(v) => setForm({ ...form, billing_period: v })}>
                  <SelectTrigger data-testid="client-period-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent className="bg-popover">
                    {PERIODS.map((p) => (
                      <SelectItem key={p.value} value={p.value} data-testid={`client-period-${p.value}`}>
                        {p.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <p className="rounded-lg bg-muted/50 px-3 py-2.5 text-xs text-muted-foreground">
              A username and a strong password are generated automatically and assigned to this restaurant's
              dashboard. The billing clock starts today, so the first payment is due one {form.billing_period === "monthly" ? "month" : form.billing_period === "quarterly" ? "quarter" : "year"} from now.
            </p>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setOpen(false)} data-testid="client-cancel-btn">
              Cancel
            </Button>
            <Button onClick={submit} disabled={busy} className="rounded-full" data-testid="client-create-btn">
              Create & generate login
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!created} onOpenChange={() => setCreated(null)}>
        <DialogContent className="bg-card">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 font-display">
              <Check className="h-5 w-5 text-emerald-600" /> {created?.name} is live
            </DialogTitle>
          </DialogHeader>
          <CredentialBox email={created?.credentials?.email} password={created?.credentials?.password} testIdPrefix="new-client-cred" />
          <p className="text-xs text-muted-foreground">
            Saved against this client, so you can look it up any time from their profile.
          </p>
          <DialogFooter>
            <Link to={created ? `/admin/clients/${created.id}` : "#"}>
              <Button className="rounded-full" data-testid="new-client-open-btn">
                Open client
              </Button>
            </Link>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminLayout>
  );
}
