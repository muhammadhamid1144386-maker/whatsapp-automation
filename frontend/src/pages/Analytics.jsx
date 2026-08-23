import { useCallback, useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Skeleton } from "@/components/ui/skeleton";
import { api, errText, money } from "@/lib/api";

export default function Analytics() {
  const [summary, setSummary] = useState(null);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/analytics/summary");
      setSummary(data);
    } catch (e) {
      toast.error(errText(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (!summary) {
    return (
      <DashboardLayout title="Analytics">
        <Skeleton className="h-96 rounded-xl" />
      </DashboardLayout>
    );
  }

  const cards = [
    { label: "Today", value: money(summary.today_sales), sub: `${summary.today_orders} orders`, testId: "analytics-today" },
    { label: "This week", value: money(summary.week_sales), sub: "last 7 days", testId: "analytics-week" },
    { label: "This month", value: money(summary.month_sales), sub: "last 30 days", testId: "analytics-month" },
    { label: "Average order", value: money(summary.average_order_value), sub: "today", testId: "analytics-aov" },
  ];

  return (
    <DashboardLayout title="Analytics" subtitle="Simple numbers you can act on">
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} data-testid={c.testId} className="card-surface p-6">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{c.label}</p>
            <p className="mt-3 font-display text-2xl font-bold tabular-nums">{c.value}</p>
            <p className="mt-1 text-xs text-muted-foreground">{c.sub}</p>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="card-surface p-6">
          <h2 className="font-display text-lg font-bold">Sales, last 7 days</h2>
          <div className="mt-6 h-64">
            {summary.daily.length === 0 ? (
              <p className="text-sm text-muted-foreground">No sales recorded yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={summary.daily}>
                  <CartesianGrid strokeOpacity={0.1} vertical={false} />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} width={48} />
                  <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                  <Line type="monotone" dataKey="sales" stroke="hsl(var(--chart-1))" strokeWidth={2.5} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="card-surface p-6">
          <h2 className="font-display text-lg font-bold">Top items</h2>
          <div className="mt-6 h-64">
            {summary.top_items.length === 0 ? (
              <p className="text-sm text-muted-foreground">No items sold yet.</p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={summary.top_items} layout="vertical">
                  <CartesianGrid strokeOpacity={0.1} horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis dataKey="name" type="category" width={130} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                  <Bar dataKey="quantity" fill="hsl(var(--chart-1))" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
