import { useCallback, useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle, DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { api, errText, money } from "@/lib/api";

const emptyItem = { name: "", description: "", price: "", image_url: "", category_id: "", available: true, addon_ids: [] };

export default function MenuPage() {
  const [menu, setMenu] = useState({ categories: [], items: [], addons: [] });
  const [loading, setLoading] = useState(true);
  const [itemOpen, setItemOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState(emptyItem);
  const [catOpen, setCatOpen] = useState(false);
  const [catName, setCatName] = useState("");

  const load = useCallback(async () => {
    try {
      const { data } = await api.get("/menu");
      setMenu(data);
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const openNew = (categoryId) => {
    setEditing(null);
    setDraft({ ...emptyItem, category_id: categoryId || menu.categories[0]?.id || "" });
    setItemOpen(true);
  };

  const openEdit = (item) => {
    setEditing(item);
    setDraft({ ...item, price: String(item.price) });
    setItemOpen(true);
  };

  const saveItem = async () => {
    const body = {
      category_id: draft.category_id,
      name: draft.name.trim(),
      description: draft.description || null,
      price: Number(draft.price),
      image_url: draft.image_url || null,
      available: draft.available,
      addon_ids: draft.addon_ids || [],
    };
    if (!body.name || !body.category_id || !Number.isFinite(body.price)) {
      toast.error("Name, category and a valid price are required");
      return;
    }
    try {
      if (editing) await api.put(`/menu/items/${editing.id}`, body);
      else await api.post("/menu/items", body);
      toast.success(editing ? "Item updated" : "Item added");
      setItemOpen(false);
      load();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  const toggleAvailable = async (item) => {
    try {
      await api.put(`/menu/items/${item.id}`, { available: !item.available });
      setMenu((m) => ({ ...m, items: m.items.map((i) => (i.id === item.id ? { ...i, available: !item.available } : i)) }));
    } catch (e) {
      toast.error(errText(e));
    }
  };

  const removeItem = async (item) => {
    try {
      await api.delete(`/menu/items/${item.id}`);
      toast.success(`${item.name} removed`);
      load();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  const addCategory = async () => {
    if (!catName.trim()) return;
    try {
      await api.post("/menu/categories", { name: catName.trim(), sort_order: menu.categories.length });
      setCatName("");
      setCatOpen(false);
      toast.success("Category added");
      load();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  const removeCategory = async (category) => {
    try {
      await api.delete(`/menu/categories/${category.id}`);
      toast.success("Category removed");
      load();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  return (
    <DashboardLayout
      title="Menu"
      subtitle="The AI can only ever sell what is listed and available here"
      actions={
        <div className="flex gap-2">
          <Dialog open={catOpen} onOpenChange={setCatOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" size="sm" className="rounded-full" data-testid="menu-add-category-btn">
                <Plus className="mr-1.5 h-3.5 w-3.5" /> Category
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-card">
              <DialogHeader>
                <DialogTitle className="font-display">New category</DialogTitle>
              </DialogHeader>
              <Input
                data-testid="category-name-input"
                value={catName}
                onChange={(e) => setCatName(e.target.value)}
                placeholder="e.g. Wraps"
              />
              <DialogFooter>
                <Button onClick={addCategory} data-testid="category-save-btn" className="rounded-full">
                  Add category
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button size="sm" className="rounded-full" data-testid="menu-add-item-btn" onClick={() => openNew()}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Item
          </Button>
        </div>
      }
    >
      {loading ? (
        <Skeleton className="h-96 rounded-xl" />
      ) : (
        <div className="space-y-8">
          {menu.categories.map((category) => {
            const items = menu.items.filter((i) => i.category_id === category.id);
            return (
              <section key={category.id} data-testid={`menu-category-${category.name}`}>
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="font-display text-lg font-bold">
                    {category.name}
                    <span className="ml-2 text-sm font-normal text-muted-foreground">{items.length} items</span>
                  </h2>
                  {items.length === 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      data-testid={`category-delete-${category.name}`}
                      onClick={() => removeCategory(category)}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
                <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                  {items.map((item) => (
                    <div key={item.id} data-testid={`menu-item-${item.name}`} className="card-surface flex gap-4 p-4">
                      {item.image_url && (
                        <img
                          src={item.image_url}
                          alt={item.name}
                          className="h-20 w-20 shrink-0 rounded-lg object-cover"
                          loading="lazy"
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-start justify-between gap-2">
                          <p className="truncate font-semibold">{item.name}</p>
                          <p className="shrink-0 font-display font-bold tabular-nums text-primary">{money(item.price)}</p>
                        </div>
                        {item.description && (
                          <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">{item.description}</p>
                        )}
                        <div className="mt-3 flex items-center gap-3">
                          <div className="flex items-center gap-1.5">
                            <Switch
                              checked={item.available}
                              onCheckedChange={() => toggleAvailable(item)}
                              data-testid={`menu-available-${item.name}`}
                            />
                            <span className="text-xs text-muted-foreground">{item.available ? "Available" : "Sold out"}</span>
                          </div>
                          {item.addon_ids?.length > 0 && (
                            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                              upsells on
                            </span>
                          )}
                          <div className="ml-auto flex gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" data-testid={`menu-edit-${item.name}`} onClick={() => openEdit(item)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 text-destructive"
                              data-testid={`menu-delete-${item.name}`}
                              onClick={() => removeItem(item)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                  <button
                    type="button"
                    onClick={() => openNew(category.id)}
                    data-testid={`menu-add-to-${category.name}`}
                    className="flex min-h-[112px] items-center justify-center gap-2 rounded-xl border border-dashed text-sm text-muted-foreground transition-colors hover:border-primary hover:text-primary"
                  >
                    <Plus className="h-4 w-4" /> Add to {category.name}
                  </button>
                </div>
              </section>
            );
          })}

          <section>
            <h2 className="mb-3 font-display text-lg font-bold">Recommended add-ons</h2>
            <div className="flex flex-wrap gap-2">
              {menu.addons.map((addon) => (
                <span
                  key={addon.id}
                  data-testid={`menu-addon-${addon.name}`}
                  className="rounded-full border bg-card px-3 py-1.5 text-sm"
                >
                  {addon.name} · <span className="tabular-nums text-muted-foreground">{money(addon.price)}</span>
                </span>
              ))}
            </div>
          </section>
        </div>
      )}

      <Dialog open={itemOpen} onOpenChange={setItemOpen}>
        <DialogContent className="max-h-[90vh] overflow-y-auto bg-card">
          <DialogHeader>
            <DialogTitle className="font-display">{editing ? `Edit ${editing.name}` : "New menu item"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Name</Label>
              <Input data-testid="item-name-input" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label>Price (PKR)</Label>
                <Input
                  data-testid="item-price-input"
                  type="number"
                  value={draft.price}
                  onChange={(e) => setDraft({ ...draft, price: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Category</Label>
                <Select value={draft.category_id} onValueChange={(v) => setDraft({ ...draft, category_id: v })}>
                  <SelectTrigger data-testid="item-category-select">
                    <SelectValue placeholder="Pick one" />
                  </SelectTrigger>
                  <SelectContent className="bg-popover">
                    {menu.categories.map((c) => (
                      <SelectItem key={c.id} value={c.id} data-testid={`item-category-option-${c.name}`}>
                        {c.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Textarea
                data-testid="item-description-input"
                rows={2}
                value={draft.description || ""}
                onChange={(e) => setDraft({ ...draft, description: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Image URL</Label>
              <Input
                data-testid="item-image-input"
                value={draft.image_url || ""}
                onChange={(e) => setDraft({ ...draft, image_url: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Recommended add-ons the AI may suggest</Label>
              <div className="flex flex-wrap gap-2">
                {menu.addons.map((addon) => {
                  const on = (draft.addon_ids || []).includes(addon.id);
                  return (
                    <button
                      key={addon.id}
                      type="button"
                      data-testid={`item-addon-toggle-${addon.name}`}
                      onClick={() =>
                        setDraft({
                          ...draft,
                          addon_ids: on
                            ? draft.addon_ids.filter((a) => a !== addon.id)
                            : [...(draft.addon_ids || []), addon.id],
                        })
                      }
                      className={`rounded-full border px-3 py-1 text-xs transition-colors ${
                        on ? "border-primary bg-primary/10 text-primary" : "hover:bg-accent"
                      }`}
                    >
                      {addon.name}
                    </button>
                  );
                })}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Switch
                checked={draft.available}
                onCheckedChange={(v) => setDraft({ ...draft, available: v })}
                data-testid="item-available-switch"
              />
              <span className="text-sm">Available for ordering</span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setItemOpen(false)} data-testid="item-cancel-btn">
              Cancel
            </Button>
            <Button onClick={saveItem} data-testid="item-save-btn" className="rounded-full">
              {editing ? "Save changes" : "Add item"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}
