export const STATUS_META = {
  NEW: { label: "New", cls: "bg-amber-100 text-amber-900 border-amber-300 dark:bg-amber-900/30 dark:text-amber-200 dark:border-amber-700" },
  CONFIRMED: { label: "Confirmed", cls: "bg-blue-100 text-blue-900 border-blue-300 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-700" },
  PREPARING: { label: "Preparing", cls: "bg-purple-100 text-purple-900 border-purple-300 dark:bg-purple-900/30 dark:text-purple-200 dark:border-purple-700" },
  READY: { label: "Ready", cls: "bg-orange-100 text-orange-900 border-orange-300 dark:bg-orange-900/30 dark:text-orange-200 dark:border-orange-700" },
  OUT_FOR_DELIVERY: { label: "Out for delivery", cls: "bg-cyan-100 text-cyan-900 border-cyan-300 dark:bg-cyan-900/30 dark:text-cyan-200 dark:border-cyan-700" },
  DELIVERED: { label: "Delivered", cls: "bg-emerald-100 text-emerald-900 border-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-200 dark:border-emerald-700" },
  REJECTED: { label: "Rejected", cls: "bg-red-100 text-red-900 border-red-300 dark:bg-red-900/30 dark:text-red-200 dark:border-red-700" },
  CANCELLED: { label: "Cancelled", cls: "bg-stone-200 text-stone-800 border-stone-300 dark:bg-stone-800 dark:text-stone-200 dark:border-stone-600" },
};

export const NEXT_ACTIONS = {
  NEW: [
    { status: "CONFIRMED", label: "Confirm", tone: "primary" },
    { status: "REJECTED", label: "Reject", tone: "danger" },
  ],
  CONFIRMED: [{ status: "PREPARING", label: "Preparing", tone: "primary" }],
  PREPARING: [{ status: "READY", label: "Ready", tone: "primary" }],
  READY: [
    { status: "OUT_FOR_DELIVERY", label: "Out for delivery", tone: "primary", deliveryOnly: true },
    { status: "DELIVERED", label: "Delivered", tone: "primary", pickupOnly: true },
  ],
  OUT_FOR_DELIVERY: [{ status: "DELIVERED", label: "Delivered", tone: "primary" }],
  DELIVERED: [],
  REJECTED: [],
  CANCELLED: [],
};

export const BOARD_COLUMNS = ["NEW", "CONFIRMED", "PREPARING", "READY", "OUT_FOR_DELIVERY", "DELIVERED"];

export const LANG_LABEL = { en: "English", ur: "اردو", roman_ur: "Roman Urdu" };
