import { useCallback, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, errText } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
// JS getDay(): 0=Sun. Backend stores python weekday(): 0=Mon.
const DAY_LABEL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function Settings() {
  const { refresh } = useAuth();
  const [restaurant, setRestaurant] = useState(null);
  const [settings, setSettings] = useState(null);
  const [openState, setOpenState] = useState({ open_now: true, opens_at: "" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/restaurant");
      setRestaurant(data.restaurant);
      setSettings(data.settings);
      setOpenState({ open_now: data.open_now, opens_at: data.opens_at });
    } catch (e) {
      toast.error(errText(e));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const saveProfile = async () => {
    setBusy(true);
    try {
      await api.put("/restaurant", {
        name: restaurant.name,
        logo_url: restaurant.logo_url,
        description: restaurant.description,
        phone: restaurant.phone,
        whatsapp_number: restaurant.whatsapp_number,
        address: restaurant.address,
        city: restaurant.city,
        currency: restaurant.currency,
        ai_greeting: restaurant.ai_greeting,
        business_rules: restaurant.business_rules,
      });
      toast.success("Profile saved");
      refresh();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const saveSettings = async () => {
    setBusy(true);
    try {
      await api.put("/restaurant/settings", {
        opening_hours: settings.opening_hours,
        delivery_areas: settings.delivery_areas,
        delivery_fee: Number(settings.delivery_fee),
        min_order: Number(settings.min_order),
        prep_time_min: Number(settings.prep_time_min),
        prep_time_max: Number(settings.prep_time_max),
        delivery_time_min: Number(settings.delivery_time_min),
        delivery_time_max: Number(settings.delivery_time_max),
        allow_orders_when_closed: settings.allow_orders_when_closed,
        upsell_enabled: settings.upsell_enabled,
        ai_active: settings.ai_active,
      });
      toast.success("Operations saved");
      load();
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setBusy(false);
    }
  };

  if (!restaurant || !settings) {
    return (
      <DashboardLayout title="Settings">
        <Skeleton className="h-96 rounded-xl" />
      </DashboardLayout>
    );
  }

  const field = (label, key, extra = {}) => (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input
        data-testid={`settings-${key}-input`}
        value={restaurant[key] ?? ""}
        onChange={(e) => setRestaurant({ ...restaurant, [key]: e.target.value })}
        {...extra}
      />
    </div>
  );

  const num = (label, key, hint) => (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input
        data-testid={`settings-${key}-input`}
        type="number"
        value={settings[key] ?? 0}
        onChange={(e) => setSettings({ ...settings, [key]: e.target.value })}
      />
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );

  const eta = {
    delivery: [
      Number(settings.prep_time_min) + Number(settings.delivery_time_min),
      Number(settings.prep_time_max) + Number(settings.delivery_time_max),
    ],
    pickup: [Number(settings.prep_time_min), Number(settings.prep_time_max)],
  };

  return (
    <DashboardLayout title="Settings" subtitle="Profile, hours, pricing rules and AI behaviour">
      <Tabs defaultValue="profile" className="max-w-4xl">
        <TabsList data-testid="settings-tabs">
          <TabsTrigger value="profile" data-testid="settings-tab-profile">Profile</TabsTrigger>
          <TabsTrigger value="operations" data-testid="settings-tab-operations">Operations</TabsTrigger>
          <TabsTrigger value="hours" data-testid="settings-tab-hours">Hours</TabsTrigger>
          <TabsTrigger value="ai" data-testid="settings-tab-ai">AI</TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-6">
          <div className="card-surface space-y-5 p-6">
            <div className="grid gap-5 sm:grid-cols-2">
              {field("Restaurant name", "name")}
              {field("City", "city")}
              {field("Phone", "phone")}
              {field("WhatsApp number", "whatsapp_number")}
              {field("Address", "address")}
              {field("Currency", "currency")}
            </div>
            {field("Logo URL", "logo_url")}
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Textarea
                data-testid="settings-description-input"
                rows={2}
                value={restaurant.description ?? ""}
                onChange={(e) => setRestaurant({ ...restaurant, description: e.target.value })}
              />
            </div>
            <Button onClick={saveProfile} disabled={busy} className="rounded-full" data-testid="settings-save-profile-btn">
              <Save className="mr-1.5 h-4 w-4" /> Save profile
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="operations" className="mt-6">
          <div className="card-surface space-y-5 p-6">
            <div className="grid gap-5 sm:grid-cols-2">
              {num("Delivery fee (PKR)", "delivery_fee")}
              {num("Minimum order (PKR)", "min_order")}
              {num("Preparation time min", "prep_time_min")}
              {num("Preparation time max", "prep_time_max")}
              {num("Delivery time min", "delivery_time_min")}
              {num("Delivery time max", "delivery_time_max")}
            </div>
            <div className="rounded-lg bg-muted/50 p-4 text-sm">
              <p className="font-medium">Quoted estimates</p>
              <p className="mt-1 text-muted-foreground" data-testid="settings-eta-preview">
                Delivery {eta.delivery[0]}–{eta.delivery[1]} minutes · Pickup {eta.pickup[0]}–{eta.pickup[1]} minutes
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                The AI is never allowed to invent times — it quotes exactly this.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label>Delivery areas (comma separated)</Label>
              <Input
                data-testid="settings-delivery-areas-input"
                value={(settings.delivery_areas || []).join(", ")}
                onChange={(e) => setSettings({ ...settings, delivery_areas: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })}
              />
            </div>
            <label className="flex items-center gap-3 text-sm">
              <Switch
                checked={settings.allow_orders_when_closed}
                onCheckedChange={(v) => setSettings({ ...settings, allow_orders_when_closed: v })}
                data-testid="settings-preorder-switch"
              />
              Accept pre-orders while closed
            </label>
            <Button onClick={saveSettings} disabled={busy} className="rounded-full" data-testid="settings-save-operations-btn">
              <Save className="mr-1.5 h-4 w-4" /> Save operations
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="hours" className="mt-6">
          <div className="card-surface space-y-4 p-6">
            <div
              data-testid="hours-live-status"
              className={`flex flex-wrap items-center gap-3 rounded-lg border px-4 py-3 text-sm ${
                openState.open_now
                  ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
                  : "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
              }`}
            >
              <span className={`h-2.5 w-2.5 rounded-full ${openState.open_now ? "bg-emerald-500" : "bg-amber-500"}`} />
              <span className="font-semibold">
                {openState.open_now ? "Open right now" : `Closed right now — opens ${openState.opens_at || "later"}`}
              </span>
              <span className="text-xs opacity-80">Times are Pakistan Standard Time (PKT)</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Outside these hours the AI assistant stops taking orders — it replies with your opening time
              instead. To keep it accepting orders while closed, turn on{" "}
              <b>Accept pre-orders while closed</b> in the Operations tab. Use 24-hour times, and a closing
              time earlier than the opening time (e.g. 18:00 → 02:00) is treated as running past midnight.
            </p>
            {(settings.opening_hours || []).map((hour, index) => (
              <div key={hour.day} className="flex flex-wrap items-center gap-3" data-testid={`hours-row-${hour.day}`}>
                <span className="w-24 text-sm font-medium">{DAY_LABEL[hour.day] || DAYS[hour.day]}</span>
                <Input
                  className="w-28"
                  data-testid={`hours-open-${hour.day}`}
                  value={hour.open}
                  onChange={(e) => {
                    const next = [...settings.opening_hours];
                    next[index] = { ...hour, open: e.target.value };
                    setSettings({ ...settings, opening_hours: next });
                  }}
                />
                <span className="text-muted-foreground">to</span>
                <Input
                  className="w-28"
                  data-testid={`hours-close-${hour.day}`}
                  value={hour.close}
                  onChange={(e) => {
                    const next = [...settings.opening_hours];
                    next[index] = { ...hour, close: e.target.value };
                    setSettings({ ...settings, opening_hours: next });
                  }}
                />
                <label className="ml-auto flex items-center gap-2 text-xs">
                  <Switch
                    checked={!hour.closed}
                    data-testid={`hours-open-switch-${hour.day}`}
                    onCheckedChange={(v) => {
                      const next = [...settings.opening_hours];
                      next[index] = { ...hour, closed: !v };
                      setSettings({ ...settings, opening_hours: next });
                    }}
                  />
                  {hour.closed ? "Closed" : "Open"}
                </label>
              </div>
            ))}
            <Button onClick={saveSettings} disabled={busy} className="rounded-full" data-testid="settings-save-hours-btn">
              <Save className="mr-1.5 h-4 w-4" /> Save hours
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="ai" className="mt-6">
          <div className="card-surface space-y-5 p-6">
            <div className="space-y-1.5">
              <Label>AI greeting</Label>
              <Textarea
                data-testid="settings-greeting-input"
                rows={2}
                value={restaurant.ai_greeting ?? ""}
                onChange={(e) => setRestaurant({ ...restaurant, ai_greeting: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Business rules the AI must respect</Label>
              <Textarea
                data-testid="settings-rules-input"
                rows={3}
                value={restaurant.business_rules ?? ""}
                onChange={(e) => setRestaurant({ ...restaurant, business_rules: e.target.value })}
              />
            </div>
            <label className="flex items-center gap-3 text-sm">
              <Switch
                checked={settings.upsell_enabled}
                onCheckedChange={(v) => setSettings({ ...settings, upsell_enabled: v })}
                data-testid="settings-upsell-switch"
              />
              Allow one complementary add-on suggestion per order
            </label>
            <label className="flex items-center gap-3 text-sm">
              <Switch
                checked={settings.ai_active}
                onCheckedChange={(v) => setSettings({ ...settings, ai_active: v })}
                data-testid="settings-ai-active-switch"
              />
              AI assistant answers new chats automatically
            </label>
            <div className="flex gap-2">
              <Button onClick={saveProfile} disabled={busy} className="rounded-full" data-testid="settings-save-ai-profile-btn">
                <Save className="mr-1.5 h-4 w-4" /> Save AI text
              </Button>
              <Button onClick={saveSettings} disabled={busy} variant="outline" className="rounded-full" data-testid="settings-save-ai-toggles-btn">
                Save toggles
              </Button>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </DashboardLayout>
  );
}
