import axios from "axios";

export const api = axios.create({
  baseURL: `${(process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "")}/api`,
});

let warming = null;
let warmedAt = 0;
export function warmBackend() {
  if (warming) return warming;
  if (Date.now() - warmedAt < 60000) return Promise.resolve();
  warming = api.get("/", { timeout: 90000 }).then(() => { warmedAt = Date.now(); })
    .catch(() => {}).finally(() => { warming = null; });
  return warming;
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ad_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiError(e, fallback = "Algo deu errado. Tente novamente.") {
  if (e?.code === "ECONNABORTED") return "O servidor demorou para responder. Tente novamente em instantes.";
  if (!e?.response) return "Não foi possível conectar ao servidor. Confira sua conexão e tente novamente.";
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => d?.msg || "").filter(Boolean).join(" ") || fallback;
  return fallback;
}

export const BRL = (v) => `R$ ${Number(v).toFixed(0)}`;

export const CATEGORY_LABELS = {
  cilios: "Cílios",
  sobrancelhas: "Sobrancelhas",
  unhas: "Unhas",
};
