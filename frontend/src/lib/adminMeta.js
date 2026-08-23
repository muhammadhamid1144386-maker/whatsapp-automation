export const SUB_STATUS = {
  active: {
    label: "Active",
    cls: "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-700",
  },
  grace: {
    label: "Grace period",
    cls: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-700",
  },
  blocked: {
    label: "Blocked",
    cls: "bg-red-100 text-red-900 border-red-300 dark:bg-red-900/30 dark:text-red-200 dark:border-red-700",
  },
  cancelled: {
    label: "Cancelled",
    cls: "bg-stone-200 text-stone-800 border-stone-300 dark:bg-stone-800 dark:text-stone-200 dark:border-stone-600",
  },
};

export const SEVERITY = {
  critical: "border-l-red-500",
  warning: "border-l-amber-500",
  success: "border-l-emerald-500",
  info: "border-l-sky-500",
};

export const PERIODS = [
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly", label: "Yearly" },
];

export const SubStatusBadge = ({ status, testId }) => {
  const meta = SUB_STATUS[status] || SUB_STATUS.cancelled;
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

export function dueLabel(sub) {
  if (!sub) return "";
  if (sub.status === "blocked") return "Blocked — payment pending";
  if (sub.days_left < 0) return `Overdue by ${Math.abs(sub.days_left)} day(s)`;
  if (sub.days_left === 0) return "Expires today";
  return `${sub.days_left} day(s) left`;
}

export function dateOnly(value) {
  if (!value) return "—";
  const iso = String(value);
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  return d.toLocaleDateString("en-PK", { day: "2-digit", month: "short", year: "numeric" });
}
