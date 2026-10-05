import { useCallback, useEffect, useRef, useState } from "react";
import { WS_URL } from "../config.js";

const MAX_EVENTS = 200;
const MAX_POINTS = 60;
const BACKOFF = [1000, 2000, 4000, 8000, 15000];

const fromEvents = (list) =>
  Object.fromEntries(list.filter((e) => e.corrected_label).map((e) => [e.id, e.corrected_label]));

/**
 * Connects to the backend WebSocket and keeps dashboard state.
 * - auto-reconnects with exponential backoff (1s -> 15s)
 * - heartbeat ping every 20s so proxies don't drop idle sockets
 * - status: "connecting" | "live" | "reconnecting"
 */
export function useEventStream() {
  const [events, setEvents] = useState([]);
  const [stats, setStats] = useState(null);
  const [series, setSeries] = useState([]);
  const [corrections, setCorrections] = useState({});   // event id -> human-corrected label
  const [status, setStatus] = useState("connecting");
  const [retryIn, setRetryIn] = useState(null);
  const attempt = useRef(0);
  const wsRef = useRef(null);
  const timers = useRef({});
  const closedByUs = useRef(false);

  const connect = useCallback(() => {
    clearTimeout(timers.current.retry);
    clearInterval(timers.current.countdown);
    setRetryIn(null);
    setStatus(attempt.current === 0 ? "connecting" : "reconnecting");

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      attempt.current = 0;
      setStatus("live");
      clearInterval(timers.current.ping);
      timers.current.ping = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 20000);
    };

    ws.onmessage = (msg) => {
      let data;
      try { data = JSON.parse(msg.data); } catch { return; }
      if (data.type === "history") {
        setEvents(data.events);
        setStats(data.stats);
        setCorrections((prev) => ({ ...prev, ...fromEvents(data.events) }));
      } else if (data.type === "feedback") {
        setCorrections((prev) => ({ ...prev, [data.event_id]: data.corrected_label }));
      } else if (data.type === "event") {
        setCorrections((prev) => ({ ...prev, ...fromEvents([data.event]) }));
        setEvents((prev) => [data.event, ...prev].slice(0, MAX_EVENTS));
      } else if (data.type === "stats") {
        setStats(data.stats);
        setSeries((prev) => [...prev, data.stats.throughput_per_sec].slice(-MAX_POINTS));
      }
    };

    ws.onclose = () => {
      clearInterval(timers.current.ping);
      if (closedByUs.current) return;
      const delay = BACKOFF[Math.min(attempt.current, BACKOFF.length - 1)];
      attempt.current += 1;
      setStatus("reconnecting");
      let left = Math.round(delay / 1000);
      setRetryIn(left);
      timers.current.countdown = setInterval(() => setRetryIn((s) => (s > 1 ? s - 1 : 1)), 1000);
      timers.current.retry = setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    closedByUs.current = false;
    connect();
    return () => {
      closedByUs.current = true;
      Object.values(timers.current).forEach((t) => { clearTimeout(t); clearInterval(t); });
      wsRef.current?.close();
    };
  }, [connect]);

  const reconnectNow = useCallback(() => {
    attempt.current = 0;
    wsRef.current?.close();
    clearTimeout(timers.current.retry);
    connect();
  }, [connect]);

  const clear = useCallback(() => setEvents([]), []);
  const markCorrected = useCallback((id, label) => setCorrections((prev) => ({ ...prev, [id]: label })), []);

  return { events, stats, series, status, retryIn, reconnectNow, clear, corrections, markCorrected };
}
