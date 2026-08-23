import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCheck, RotateCcw, Send, Wifi } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errText } from "@/lib/api";
import { useCustomerStream } from "@/hooks/useRealtime";

const QUICK = ["Hi", "Menu dikhayen", "1 zinger burger aur fries", "Delivery", "Confirm"];

export const WhatsAppSimulator = ({ slug = "pizza-palace", phone = "03001234567", compact = false }) => {
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [info, setInfo] = useState(null);
  const scroller = useRef(null);

  const load = useCallback(async () => {
    try {
      const [{ data: profile }, { data: history }] = await Promise.all([
        api.get(`/chat/${slug}`),
        api.get(`/chat/${slug}/history`, { params: { phone } }),
      ]);
      setInfo(profile);
      setMessages(history.messages || []);
    } catch (e) {
      toast.error(errText(e));
    }
  }, [slug, phone]);

  useEffect(() => {
    load();
  }, [load]);

  useCustomerStream(slug, phone, (event, data) => {
    if (event === "WHATSAPP_MESSAGE") {
      setMessages((prev) =>
        prev.some((m) => m.body === data.body && m.sender !== "customer" && Date.now() - (m._t || 0) < 3000)
          ? prev
          : [...prev, { id: `live-${Date.now()}-${Math.random()}`, sender: data.sender || "ai", body: data.body, created_at: new Date().toISOString(), _t: Date.now() }],
      );
    }
  });

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const send = async (text) => {
    const body = (text ?? draft).trim();
    if (!body || sending) return;
    setDraft("");
    setSending(true);
    setMessages((prev) => [...prev, { id: `local-${Date.now()}`, sender: "customer", body, created_at: new Date().toISOString() }]);
    try {
      const { data } = await api.post(`/chat/${slug}/message`, {
        phone,
        text: body,
        client_message_id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      });
      if (data.handoff) toast.info("A human has taken over this chat — the AI is paused.");
      const replies = data.replies || [];
      setMessages((prev) => {
        const existing = new Set(prev.map((m) => m.body));
        const extra = replies.filter((r) => !existing.has(r)).map((r, i) => ({
          id: `ai-${Date.now()}-${i}`, sender: "ai", body: r, created_at: new Date().toISOString(),
        }));
        return [...prev, ...extra];
      });
    } catch (e) {
      toast.error(errText(e));
    } finally {
      setSending(false);
    }
  };

  const reset = async () => {
    try {
      await api.post(`/chat/${slug}/reset`, null, { params: { phone } });
      setMessages([]);
      toast.success("Chat reset — start the demo again");
    } catch (e) {
      toast.error(errText(e));
    }
  };

  return (
    <div
      data-testid="whatsapp-simulator"
      className={`relative flex w-full flex-col overflow-hidden rounded-[2rem] border-[6px] border-stone-800 bg-[#EFEAE2] shadow-2xl dark:border-stone-700 ${
        compact ? "h-[600px]" : "h-[680px]"
      }`}
    >
      <div className="flex items-center gap-3 bg-[#075E54] px-4 py-3 text-white">
        <div className="grid h-9 w-9 place-items-center overflow-hidden rounded-full bg-white/20 text-sm font-bold">
          {info?.logo_url ? (
            <img src={info.logo_url} alt={info?.name} className="h-full w-full object-cover" />
          ) : (
            "PP"
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{info?.name || "Restaurant"}</p>
          <p className="flex items-center gap-1 text-[11px] text-emerald-200">
          <Wifi className="h-3 w-3" />
          {info?.open_now === false
            ? `closed · opens ${info?.opens_at || "later"}`
            : info?.channel_status === "connected"
              ? "online · AI assistant"
              : "channel not connected"}
        </p>
        </div>
        <button
          type="button"
          data-testid="simulator-reset-btn"
          onClick={reset}
          title="Reset chat"
          className="rounded-full p-2 transition-colors hover:bg-white/15"
        >
          <RotateCcw className="h-4 w-4" />
        </button>
      </div>

      <div ref={scroller} className="wa-bg scroll-thin flex-1 space-y-2 overflow-y-auto px-3 py-4">
        {messages.length === 0 && (
          <div className="mx-auto max-w-[85%] rounded-lg bg-[#FFF6D8] px-3 py-2 text-center text-[11px] text-stone-600 shadow-sm">
            Send “Hi” to start. Try English, Urdu or Roman Urdu.
          </div>
        )}
        {messages.map((m) => {
          const mine = m.sender === "customer";
          const urdu = /[\u0600-\u06FF]/.test(m.body || "");
          return (
            <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div
                data-testid={`sim-msg-${m.sender}`}
                className={`max-w-[82%] whitespace-pre-wrap px-2.5 py-1.5 text-[13px] leading-relaxed shadow-sm ${
                  mine
                    ? "rounded-lg rounded-tr-none bg-[#D9FDD3] text-slate-900"
                    : "rounded-lg rounded-tl-none bg-white text-slate-900"
                } ${urdu ? "font-urdu text-right" : ""}`}
              >
                {m.body}
                {mine && <CheckCheck className="ml-1 inline h-3 w-3 text-sky-600" />}
              </div>
            </div>
          );
        })}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-lg rounded-tl-none bg-white px-3 py-2 text-[13px] text-stone-400 shadow-sm">
              typing…
            </div>
          </div>
        )}
      </div>

      <div className="border-t border-stone-300 bg-[#F0F2F5] px-2 py-2">
        <div className="mb-2 flex gap-1.5 overflow-x-auto scroll-thin">
          {QUICK.map((q) => (
            <button
              key={q}
              type="button"
              data-testid={`sim-quick-${q.toLowerCase().replace(/\s+/g, "-")}`}
              onClick={() => send(q)}
              disabled={sending}
              className="shrink-0 rounded-full border border-stone-300 bg-white px-2.5 py-1 text-[11px] text-stone-700 transition-colors hover:bg-stone-100 disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <Input
            data-testid="simulator-input"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Type a message"
            className="h-10 rounded-full border-stone-300 bg-white text-slate-900 placeholder:text-stone-400"
          />
          <Button
            type="submit"
            size="icon"
            data-testid="simulator-send-btn"
            disabled={sending || !draft.trim()}
            className="h-10 w-10 shrink-0 rounded-full bg-[#25D366] text-white hover:bg-[#1eb757]"
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
        <p className="mt-1.5 text-center text-[10px] text-stone-500">
          Simulator · {phone} · no real WhatsApp account is used
        </p>
      </div>
    </div>
  );
};
