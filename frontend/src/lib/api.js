import axios from "axios";

export const api = axios.create({
  baseURL: `${(process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "")}/api`,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ad_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiError(e, fallback = "Algo deu errado. Tente novamente.") {
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
