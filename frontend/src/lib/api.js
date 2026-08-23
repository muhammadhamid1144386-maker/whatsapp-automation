import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, withCredentials: true });

const TOKEN_KEY = "ara_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiError(detail) {
  if (detail == null) return "Something went wrong. Please try again.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export function errText(e) {
  return apiError(e?.response?.data?.detail) || e?.message || "Request failed";
}

export const money = (value) =>
  `PKR ${Number(value || 0).toLocaleString("en-PK", { maximumFractionDigits: 0 })}`;

export function timeAgo(iso) {
  if (!iso) return "";
  const then = new Date(iso.endsWith?.("Z") || iso.includes?.("+") ? iso : `${iso}Z`).getTime();
  const mins = Math.max(0, Math.floor((Date.now() - then) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function clockTime(iso) {
  if (!iso) return "";
  const d = new Date(iso.endsWith?.("Z") || iso.includes?.("+") ? iso : `${iso}Z`);
  return d.toLocaleTimeString("en-PK", { hour: "2-digit", minute: "2-digit" });
}
