import { useEffect, useRef } from "react";
import { API, getToken } from "@/lib/api";

/** Subscribes to the restaurant dashboard SSE stream. */
export function useDashboardStream(onEvent, enabled = true) {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!enabled) return undefined;
    const token = getToken();
    if (!token) return undefined;
    const source = new EventSource(`${API}/events/stream?token=${encodeURIComponent(token)}`);
    source.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data);
        handler.current?.(payload.event, payload.data);
      } catch {
        /* heartbeat */
      }
    };
    source.onerror = () => {
      /* EventSource retries automatically */
    };
    return () => source.close();
  }, [enabled]);
}

/** Subscribes to a single customer's notification stream (used by the simulator). */
export function useCustomerStream(slug, phone, onEvent) {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!slug || !phone) return undefined;
    const source = new EventSource(`${API}/chat/${slug}/stream?phone=${encodeURIComponent(phone)}`);
    source.onmessage = (message) => {
      try {
        const payload = JSON.parse(message.data);
        handler.current?.(payload.event, payload.data);
      } catch {
        /* heartbeat */
      }
    };
    return () => source.close();
  }, [slug, phone]);
}

let audioCtx = null;
export function playNewOrderChime() {
  try {
    audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
    const now = audioCtx.currentTime;
    [880, 1174].forEach((freq, i) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(0.0001, now + i * 0.16);
      gain.gain.exponentialRampToValueAtTime(0.14, now + i * 0.16 + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.16 + 0.3);
      osc.connect(gain).connect(audioCtx.destination);
      osc.start(now + i * 0.16);
      osc.stop(now + i * 0.16 + 0.32);
    });
  } catch {
    /* audio blocked before first interaction */
  }
}
