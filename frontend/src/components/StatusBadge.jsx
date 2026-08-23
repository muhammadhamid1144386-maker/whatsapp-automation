import { STATUS_META } from "@/lib/orderMeta";

export const StatusBadge = ({ status, testId }) => {
  const meta = STATUS_META[status] || { label: status, cls: "bg-muted text-foreground border-border" };
  return (
    <span
      data-testid={testId}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-semibold ${meta.cls}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70" />
      {meta.label}
    </span>
  );
};
