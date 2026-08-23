import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, Search, Volume2, VolumeX } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { OrderCard } from "@/components/OrderCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errText } from "@/lib/api";
import { BOARD_COLUMNS, STATUS_META } from "@/lib/orderMeta";
import { useDashboardStream } from "@/hooks/useRealtime";

export default function Orders() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sound, setSound] = useState(true);
  const fresh = useRef(new Set());

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/orders", { params: { limit: 200, search: search || undefined } });
      setOrders(data);
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setLoading(false);
    }
  }, [search]);

  useEffect(() => {
    load();
  }, [load]);

  useDashboardStream((event, data) => {
    if (event === "NEW_ORDER") {
      fresh.current.add(data.order_number);
      setTimeout(() => fresh.current.delete(data.order_number), 6000);
    }
    if (event === "NEW_ORDER" || event.startsWith("ORDER_")) load();
  });

  const columns = BOARD_COLUMNS.map((status) => ({
    status,
    label: STATUS_META[status].label,
    items: orders.filter((o) => o.status === status),
  }));
  const closed = orders.filter((o) => ["REJECTED", "CANCELLED"].includes(o.status));

  return (
    <DashboardLayout
      title="Live orders"
      subtitle="New orders appear here automatically — no refresh needed"
      actions={
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            className="rounded-full"
            data-testid="orders-sound-toggle"
            title={sound ? "Mute new order sound" : "Unmute"}
            onClick={() => setSound((s) => !s)}
          >
            {sound ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
          </Button>
          <Button variant="outline" size="sm" className="rounded-full" data-testid="orders-refresh-btn" onClick={load}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" /> Refresh
          </Button>
        </div>
      }
    >
      <div className="relative mb-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          data-testid="orders-search-input"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search order number, name or phone"
          className="pl-9"
        />
      </div>

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <Skeleton key={i} className="h-56 rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="flex snap-x gap-5 overflow-x-auto scroll-thin pb-6">
          {columns.map((column) => (
            <div key={column.status} className="flex w-[330px] shrink-0 snap-start flex-col gap-3" data-testid={`board-column-${column.status}`}>
              <div className="flex items-center justify-between px-1">
                <h3 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">{column.label}</h3>
                <span
                  data-testid={`board-count-${column.status}`}
                  className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold tabular-nums"
                >
                  {column.items.length}
                </span>
              </div>
              {column.items.length === 0 ? (
                <div className="rounded-xl border border-dashed p-6 text-center text-xs text-muted-foreground">
                  Nothing here
                </div>
              ) : (
                column.items.map((order) => (
                  <OrderCard key={order.id} order={order} onChanged={load} fresh={fresh.current.has(order.order_number)} />
                ))
              )}
            </div>
          ))}
        </div>
      )}

      {closed.length > 0 && (
        <div className="mt-8">
          <h3 className="mb-3 text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Rejected & cancelled
          </h3>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {closed.map((order) => (
              <OrderCard key={order.id} order={order} onChanged={load} />
            ))}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
