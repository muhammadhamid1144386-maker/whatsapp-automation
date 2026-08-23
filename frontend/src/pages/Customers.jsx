import { useCallback, useEffect, useState } from "react";
import { Search, Users } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errText, money, timeAgo } from "@/lib/api";

export default function Customers() {
  const [customers, setCustomers] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/customers", { params: { search: search || undefined } });
      setCustomers(data);
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <DashboardLayout title="Customers" subtitle="Everyone who has messaged your WhatsApp">
      <div className="relative mb-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          data-testid="customers-search-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search name or phone"
          className="pl-9"
        />
      </div>

      {loading ? (
        <Skeleton className="h-72 rounded-xl" />
      ) : customers.length === 0 ? (
        <div className="card-surface flex flex-col items-center px-6 py-16 text-center">
          <Users className="h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            No customers yet. They appear automatically after their first WhatsApp message.
          </p>
        </div>
      ) : (
        <div className="card-surface overflow-x-auto">
          <table className="w-full text-sm" data-testid="customers-table">
            <thead>
              <tr className="border-b text-xs uppercase tracking-wider text-muted-foreground">
                <th className="px-6 py-3 text-left font-semibold">Customer</th>
                <th className="px-6 py-3 text-left font-semibold">Phone</th>
                <th className="px-6 py-3 text-right font-semibold">Orders</th>
                <th className="px-6 py-3 text-right font-semibold">Total spent</th>
                <th className="px-6 py-3 text-right font-semibold">Last order</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {customers.map((customer) => (
                <tr key={customer.id} data-testid={`customer-row-${customer.phone}`} className="transition-colors hover:bg-accent/40">
                  <td className="px-6 py-3.5 font-medium">{customer.name || "Unknown"}</td>
                  <td className="px-6 py-3.5 font-mono-plex text-xs text-muted-foreground">{customer.phone}</td>
                  <td className="px-6 py-3.5 text-right tabular-nums">{customer.total_orders}</td>
                  <td className="px-6 py-3.5 text-right tabular-nums font-medium">{money(customer.total_spent)}</td>
                  <td className="px-6 py-3.5 text-right text-xs text-muted-foreground">
                    {customer.last_order_at ? timeAgo(customer.last_order_at) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </DashboardLayout>
  );
}
