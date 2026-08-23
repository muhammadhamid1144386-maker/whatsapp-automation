import { useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import {
  BarChart3, ChefHat, LayoutDashboard, LogOut, Menu as MenuIcon, MessageSquare,
  Moon, Receipt, Settings as SettingsIcon, Sheet, Sun, Users, X, Smartphone,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { playNewOrderChime, useDashboardStream } from "@/hooks/useRealtime";
import { Button } from "@/components/ui/button";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testId: "nav-dashboard" },
  { to: "/orders", label: "Orders", icon: Receipt, testId: "nav-orders" },
  { to: "/customers", label: "Customers", icon: Users, testId: "nav-customers" },
  { to: "/menu", label: "Menu", icon: ChefHat, testId: "nav-menu" },
  { to: "/conversations", label: "Conversations", icon: MessageSquare, testId: "nav-conversations" },
  { to: "/whatsapp", label: "WhatsApp", icon: Smartphone, testId: "nav-whatsapp" },
  { to: "/google-sheets", label: "Google Sheets", icon: Sheet, testId: "nav-google-sheets" },
  { to: "/analytics", label: "Analytics", icon: BarChart3, testId: "nav-analytics" },
  { to: "/settings", label: "Settings", icon: SettingsIcon, testId: "nav-settings" },
];

export const DashboardLayout = ({ children, title, subtitle, actions }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [dark, setDark] = useState(() => localStorage.getItem("ara_theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("ara_theme", dark ? "dark" : "light");
  }, [dark]);

  useDashboardStream((event, data) => {
    if (event === "NEW_ORDER") {
      playNewOrderChime();
      toast.success(`New Order ${data.order_number}`, {
        description: `${data.customer_name} · PKR ${Number(data.total).toLocaleString()} · ${data.order_type}`,
        action: { label: "Open", onClick: () => navigate(`/orders/${data.id}`) },
      });
    } else if (event === "HUMAN_HANDOFF") {
      toast.warning("A customer asked for a human", { description: data.phone });
    } else if (event === "AI_ERROR") {
      toast.error("AI assistant could not reply", { description: data.reason });
    }
  });

  return (
    <div className="min-h-screen bg-background">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-64 border-r bg-card transition-transform duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b px-5">
          <Link to="/dashboard" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground">
              <ChefHat className="h-4 w-4" />
            </span>
            <span className="font-display text-base font-bold leading-tight">
              AI Restaurant
              <span className="block text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
                Assistant
              </span>
            </span>
          </Link>
          <button className="lg:hidden" onClick={() => setOpen(false)} data-testid="sidebar-close-btn">
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="space-y-1 p-3">
          {NAV.map(({ to, label, icon: Icon, testId }) => (
            <NavLink
              key={to}
              to={to}
              data-testid={testId}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="absolute inset-x-0 bottom-0 border-t p-3">
          <div className="mb-2 px-2">
            <p className="truncate text-sm font-semibold">{user?.restaurant?.name}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 rounded-full"
              data-testid="theme-toggle-btn"
              onClick={() => setDark((d) => !d)}
            >
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 rounded-full"
              data-testid="logout-btn"
              onClick={async () => {
                await logout();
                navigate("/login");
              }}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </aside>

      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}

      <div className="lg:pl-64">
        <header className="glass-header sticky top-0 z-20 flex h-16 items-center gap-4 border-b px-4 sm:px-6">
          <button className="lg:hidden" onClick={() => setOpen(true)} data-testid="sidebar-open-btn">
            <MenuIcon className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 data-testid="page-title" className="truncate font-display text-xl font-bold sm:text-2xl">
              {title}
            </h1>
            {subtitle && <p className="truncate text-xs text-muted-foreground sm:text-sm">{subtitle}</p>}
          </div>
          {actions}
        </header>
        <main className="p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
};
