import { useCallback, useEffect, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Bell, LayoutDashboard, LogOut, Menu as MenuIcon, Moon, ShieldCheck, Sun, Users, X } from "lucide-react";
import { toast } from "sonner";
import { api, errText } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { SEVERITY, dateOnly } from "@/lib/adminMeta";
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";

const NAV = [
  { to: "/admin", label: "Overview", icon: LayoutDashboard, testId: "admin-nav-overview", end: true },
  { to: "/admin/clients", label: "Clients", icon: Users, testId: "admin-nav-clients" },
];

export const AdminLayout = ({ children, title, subtitle, actions }) => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState({ unread: 0, alerts: [] });
  const [dark, setDark] = useState(() => localStorage.getItem("ara_theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("ara_theme", dark ? "dark" : "light");
  }, [dark]);

  const loadAlerts = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/alerts", { params: { limit: 40 } });
      setAlerts(data);
    } catch (e) {
      toast.error(errText(e));
    }
  }, []);

  useEffect(() => {
    loadAlerts();
    const timer = setInterval(loadAlerts, 60000);
    return () => clearInterval(timer);
  }, [loadAlerts]);

  const markRead = async () => {
    try {
      await api.post("/admin/alerts/read");
      loadAlerts();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <aside
        className={`fixed inset-y-0 left-0 z-40 w-60 border-r bg-[#141311] text-stone-200 transition-transform duration-200 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center justify-between border-b border-white/10 px-5">
          <Link to="/admin" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-primary-foreground">
              <ShieldCheck className="h-4 w-4" />
            </span>
            <span className="font-display text-sm font-bold leading-tight">
              Platform Console
              <span className="block text-[10px] font-medium uppercase tracking-widest text-stone-400">
                Owner access
              </span>
            </span>
          </Link>
          <button className="lg:hidden" onClick={() => setOpen(false)} data-testid="admin-sidebar-close">
            <X className="h-5 w-5" />
          </button>
        </div>
        <nav className="space-y-1 p-3">
          {NAV.map(({ to, label, icon: Icon, testId, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              data-testid={testId}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                  isActive ? "bg-primary/20 text-primary" : "text-stone-400 hover:bg-white/5 hover:text-stone-100"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="absolute inset-x-0 bottom-0 border-t border-white/10 p-3">
          <p className="truncate px-2 text-xs text-stone-400">{user?.email}</p>
          <div className="mt-2 flex gap-2">
            <Button variant="outline" size="sm" className="flex-1 rounded-full border-white/20 bg-transparent text-stone-200 hover:bg-white/10" onClick={() => setDark((d) => !d)} data-testid="admin-theme-toggle">
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 rounded-full border-white/20 bg-transparent text-stone-200 hover:bg-white/10"
              data-testid="admin-logout-btn"
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

      <div className="lg:pl-60">
        <header className="glass-header sticky top-0 z-20 flex h-16 items-center gap-3 border-b px-4 sm:px-6">
          <button className="lg:hidden" onClick={() => setOpen(true)} data-testid="admin-sidebar-open">
            <MenuIcon className="h-5 w-5" />
          </button>
          <div className="min-w-0 flex-1">
            <h1 data-testid="admin-page-title" className="truncate font-display text-xl font-bold sm:text-2xl">
              {title}
            </h1>
            {subtitle && <p className="truncate text-xs text-muted-foreground sm:text-sm">{subtitle}</p>}
          </div>
          {actions}
          <Sheet>
            <SheetTrigger asChild>
              <Button variant="outline" size="icon" className="relative shrink-0 rounded-full" data-testid="admin-alerts-btn">
                <Bell className="h-4 w-4" />
                {alerts.unread > 0 && (
                  <span
                    data-testid="admin-alerts-count"
                    className="absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground"
                  >
                    {alerts.unread}
                  </span>
                )}
              </Button>
            </SheetTrigger>
            <SheetContent className="w-full overflow-y-auto bg-card sm:max-w-md">
              <SheetHeader>
                <SheetTitle className="font-display">Notifications</SheetTitle>
              </SheetHeader>
              <div className="mt-4 flex items-center justify-between">
                <p className="text-xs text-muted-foreground">{alerts.unread} unread</p>
                <Button variant="ghost" size="sm" onClick={markRead} data-testid="admin-alerts-mark-read">
                  Mark all read
                </Button>
              </div>
              <div className="mt-3 space-y-2" data-testid="admin-alerts-list">
                {alerts.alerts.length === 0 && (
                  <p className="py-8 text-center text-sm text-muted-foreground">Nothing to report yet.</p>
                )}
                {alerts.alerts.map((alert) => (
                  <div
                    key={alert.id}
                    data-testid={`admin-alert-${alert.kind}`}
                    className={`rounded-lg border border-l-4 bg-muted/40 px-3 py-2.5 ${SEVERITY[alert.severity] || SEVERITY.info} ${
                      alert.read ? "opacity-60" : ""
                    }`}
                  >
                    <p className="text-sm">{alert.message}</p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {alert.restaurant_name} · {dateOnly(alert.created_at)}
                    </p>
                  </div>
                ))}
              </div>
            </SheetContent>
          </Sheet>
        </header>
        <main className="p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
};
