import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Bot, MessageSquare, Send, UserCog } from "lucide-react";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { api, clockTime, errText, timeAgo } from "@/lib/api";
import { LANG_LABEL } from "@/lib/orderMeta";
import { useDashboardStream } from "@/hooks/useRealtime";

export default function Conversations() {
  const [params, setParams] = useSearchParams();
  const activeId = params.get("id");
  const [list, setList] = useState([]);
  const [thread, setThread] = useState(null);
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const scroller = useRef(null);

  const loadList = useCallback(async () => {
    try {
      const { data } = await api.get("/conversations");
      setList(data);
      if (!activeId && data.length) setParams({ id: data[0].id }, { replace: true });
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setLoading(false);
    }
  }, [activeId, setParams]);

  const loadThread = useCallback(async () => {
    if (!activeId) return;
    try {
      const { data } = await api.get(`/conversations/${activeId}`);
      setThread(data);
    } catch (e) {
      toast.error(errText(e));
    }
  }, [activeId]);

  useEffect(() => {
    loadList();
  }, [loadList]);
  useEffect(() => {
    loadThread();
  }, [loadThread]);

  useDashboardStream((event, data) => {
    if (event === "NEW_MESSAGE" || event === "NEW_CONVERSATION" || event === "HUMAN_HANDOFF") {
      loadList();
      if (!data?.conversation_id || data.conversation_id === activeId) loadThread();
    }
  });

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [thread]);

  const toggleAi = async (value) => {
    try {
      await api.post(`/conversations/${activeId}/handoff`, { ai_active: value });
      toast.success(value ? "AI resumed" : "You have taken over this chat");
      loadThread();
      loadList();
    } catch (e) {
      toast.error(errText(e));
    }
  };

  const sendReply = async (e) => {
    e.preventDefault();
    if (!draft.trim()) return;
    try {
      await api.post(`/conversations/${activeId}/reply`, { body: draft.trim() });
      setDraft("");
      loadThread();
    } catch (e2) {
      toast.error(errText(e2));
    }
  };

  const conversation = thread?.conversation;

  return (
    <DashboardLayout title="Conversations" subtitle="Every WhatsApp chat, with AI / human control">
      {loading ? (
        <Skeleton className="h-[600px] rounded-xl" />
      ) : list.length === 0 ? (
        <div className="card-surface flex flex-col items-center px-6 py-16 text-center">
          <MessageSquare className="h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">
            No conversations yet. Open the WhatsApp simulator and send a message.
          </p>
        </div>
      ) : (
        <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
          <div className="card-surface max-h-[70vh] divide-y overflow-y-auto scroll-thin" data-testid="conversation-list">
            {list.map((item) => (
              <button
                key={item.id}
                type="button"
                data-testid={`conversation-item-${item.phone}`}
                onClick={() => setParams({ id: item.id })}
                className={`w-full px-4 py-3.5 text-left transition-colors ${
                  item.id === activeId ? "bg-primary/10" : "hover:bg-accent/50"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="truncate text-sm font-semibold">{item.customer_name || item.phone}</p>
                  <span className="shrink-0 text-[10px] text-muted-foreground">{timeAgo(item.last_message_at)}</span>
                </div>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">{item.last_message || "No messages"}</p>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <span
                    className={`rounded-full px-1.5 py-0.5 text-[10px] font-semibold ${
                      item.ai_active
                        ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200"
                        : "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200"
                    }`}
                  >
                    {item.ai_active ? "AI" : "Human"}
                  </span>
                  <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    {item.state?.replace(/_/g, " ").toLowerCase()}
                  </span>
                </div>
              </button>
            ))}
          </div>

          <div className="card-surface flex max-h-[70vh] flex-col overflow-hidden">
            {!conversation ? (
              <div className="grid flex-1 place-items-center p-8 text-sm text-muted-foreground">
                Pick a conversation
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 border-b px-5 py-4">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-semibold">{thread.customer?.name || conversation.phone}</p>
                    <p className="text-xs text-muted-foreground">
                      {conversation.phone} · {LANG_LABEL[conversation.language] || conversation.language} ·{" "}
                      {thread.orders.length} orders
                    </p>
                  </div>
                  <div className="flex items-center gap-2 rounded-full border px-3 py-1.5">
                    {conversation.ai_active ? (
                      <Bot className="h-4 w-4 text-emerald-600" />
                    ) : (
                      <UserCog className="h-4 w-4 text-amber-600" />
                    )}
                    <span className="text-xs font-medium">{conversation.ai_active ? "AI active" : "Human active"}</span>
                    <Switch
                      checked={conversation.ai_active}
                      onCheckedChange={toggleAi}
                      data-testid="conversation-ai-toggle"
                    />
                  </div>
                </div>

                <div ref={scroller} className="wa-bg scroll-thin flex-1 space-y-2 overflow-y-auto p-4">
                  {thread.messages.map((message) => {
                    const mine = message.sender !== "customer";
                    const urdu = /[\u0600-\u06FF]/.test(message.body || "");
                    return (
                      <div key={message.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                        <div
                          data-testid={`thread-msg-${message.sender}`}
                          className={`max-w-[75%] whitespace-pre-wrap px-3 py-2 text-[13px] shadow-sm ${
                            mine
                              ? "rounded-lg rounded-tr-none bg-[#D9FDD3] text-slate-900"
                              : "rounded-lg rounded-tl-none bg-white text-slate-900"
                          } ${urdu ? "font-urdu text-right" : ""}`}
                        >
                          {message.body}
                          <span className="ml-2 align-bottom text-[10px] text-slate-500">
                            {message.sender === "staff" ? "staff · " : message.sender === "ai" ? "AI · " : ""}
                            {clockTime(message.created_at)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                <form onSubmit={sendReply} className="flex items-center gap-2 border-t px-4 py-3">
                  <Input
                    data-testid="conversation-reply-input"
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    placeholder={conversation.ai_active ? "Turn off AI to reply as staff" : "Reply as staff…"}
                    disabled={conversation.ai_active}
                  />
                  <Button
                    type="submit"
                    size="icon"
                    className="shrink-0 rounded-full"
                    data-testid="conversation-reply-btn"
                    disabled={conversation.ai_active || !draft.trim()}
                  >
                    <Send className="h-4 w-4" />
                  </Button>
                </form>
              </>
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
