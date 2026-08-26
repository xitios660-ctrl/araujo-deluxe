import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  ArrowLeft,
  Bell,
  Clapperboard,
  Loader2,
  LogOut,
  Lock,
  RefreshCw,
} from "lucide-react";
import { brand, formatBRL } from "../mock";

const API = process.env.REACT_APP_BACKEND_URL;

const STATUS_OPTIONS = [
  { id: "aguardando_pagamento", label: "Aguardando pagamento", color: "text-amber-300 border-amber-400/40 bg-amber-400/10" },
  { id: "pago", label: "Pago", color: "text-emerald-300 border-emerald-400/40 bg-emerald-400/10" },
  { id: "em_preparacao", label: "Em preparação", color: "text-violet-300 border-violet-400/40 bg-violet-500/10" },
  { id: "enviado", label: "Enviado", color: "text-sky-300 border-sky-400/40 bg-sky-400/10" },
  { id: "entregue", label: "Entregue", color: "text-white/80 border-white/25 bg-white/10" },
];

const inputCls =
  "h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white placeholder:text-white/30 focus:border-violet-500/60 focus:outline-none focus:ring-2 focus:ring-violet-600/30";

const fmtDate = (iso) => {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    });
  } catch (e) {
    return "";
  }
};

const playChime = () => {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    [880, 1174.66, 1567.98].forEach((f, i) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.type = "sine";
      o.frequency.value = f;
      const t = ctx.currentTime + i * 0.16;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.22, t + 0.03);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.55);
      o.connect(g).connect(ctx.destination);
      o.start(t);
      o.stop(t + 0.6);
    });
  } catch (e) {
    /* audio blocked */
  }
};

export default function Admin() {
  const [user, setUser] = useState(null); // null=checking, false=guest, obj=logged
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [logging, setLogging] = useState(false);
  const [orders, setOrders] = useState([]);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [newCount, setNewCount] = useState(0);
  const knownRef = useRef(null);

  const loadOrders = useCallback(async (silent = false) => {
    if (!silent) setLoadingOrders(true);
    try {
      const r = await axios.get(`${API}/api/admin/orders`, { withCredentials: true });
      if (knownRef.current) {
        const fresh = r.data.filter((o) => !knownRef.current.has(o.order_number));
        if (fresh.length > 0) {
          setNewCount((c) => c + fresh.length);
          playChime();
          fresh.forEach((o) =>
            toast.success(`Novo pedido ${o.order_number}`, {
              description: `${o.customer.name} — ${new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(o.total)}`,
              duration: 8000,
            })
          );
        }
      }
      knownRef.current = new Set(r.data.map((o) => o.order_number));
      setOrders(r.data);
    } catch (e) {
      if (e?.response?.status === 401) setUser(false);
      else if (!silent) toast.error("Erro ao carregar pedidos.");
    } finally {
      if (!silent) setLoadingOrders(false);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    const id = setInterval(() => loadOrders(true), 15000);
    return () => clearInterval(id);
  }, [user, loadOrders]);

  useEffect(() => {
    const saved = localStorage.getItem("ddc_token");
    if (saved) axios.defaults.headers.common["Authorization"] = `Bearer ${saved}`;
    axios
      .get(`${API}/api/auth/me`, { withCredentials: true })
      .then((r) => {
        setUser(r.data);
        loadOrders();
      })
      .catch(() => setUser(false));
  }, [loadOrders]);

  const login = async (e) => {
    e.preventDefault();
    setLogging(true);
    setLoginError("");
    try {
      const r = await axios.post(
        `${API}/api/auth/login`,
        { email, password },
        { withCredentials: true }
      );
      axios.defaults.headers.common["Authorization"] = `Bearer ${r.data.access_token}`;
      localStorage.setItem("ddc_token", r.data.access_token);
      setUser(r.data);
      loadOrders();
    } catch (err) {
      const d = err?.response?.data?.detail;
      setLoginError(typeof d === "string" ? d : "Falha no login. Tente novamente.");
    } finally {
      setLogging(false);
    }
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/api/auth/logout`, {}, { withCredentials: true });
    } catch (e) {
      /* ignore */
    }
    delete axios.defaults.headers.common["Authorization"];
    localStorage.removeItem("ddc_token");
    setUser(false);
    setOrders([]);
  };

  const changeStatus = async (orderNumber, status) => {
    const prev = orders;
    setOrders((os) => os.map((o) => (o.order_number === orderNumber ? { ...o, status } : o)));
    try {
      await axios.patch(
        `${API}/api/admin/orders/${orderNumber}/status`,
        { status },
        { withCredentials: true }
      );
      toast.success(`${orderNumber} → ${STATUS_OPTIONS.find((s) => s.id === status)?.label}`);
    } catch (e) {
      setOrders(prev);
      toast.error("Não foi possível atualizar o status.");
    }
  };

  if (user === null) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
      </div>
    );
  }

  if (user === false) {
    return (
      <div className="relative flex min-h-screen items-center justify-center px-4" data-testid="admin-login-page">
        <div className="film-grain" />
        <div className="cinema-bg pointer-events-none fixed inset-0 opacity-60" />
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass relative z-10 w-full max-w-sm rounded-3xl p-7"
        >
          <div className="mb-6 flex flex-col items-center text-center">
            <span className="mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-purple-800 shadow-lg shadow-violet-900/50">
              <Lock className="h-6 w-6 text-white" />
            </span>
            <p className="text-[10px] font-semibold uppercase tracking-[0.4em] text-amber-300">
              {brand.name}
            </p>
            <h1 className="font-display text-3xl text-white">DIREÇÃO</h1>
            <p className="mt-1 text-xs text-white/40">Área restrita da equipe</p>
          </div>
          <form onSubmit={login} className="flex flex-col gap-3">
            <input
              data-testid="admin-email-input"
              className={inputCls}
              placeholder="E-mail"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <input
              data-testid="admin-password-input"
              className={inputCls}
              placeholder="Senha"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            {loginError && (
              <p data-testid="admin-login-error" className="text-xs text-red-400">
                {loginError}
              </p>
            )}
            <button
              data-testid="admin-login-button"
              type="submit"
              disabled={logging}
              className="mt-1 flex items-center justify-center gap-2 rounded-full bg-gradient-to-r from-violet-600 to-purple-500 px-6 py-3.5 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-violet-900/40 transition-transform hover:scale-[1.02] disabled:opacity-60"
            >
              {logging ? <Loader2 className="h-4 w-4 animate-spin" /> : <Clapperboard className="h-4 w-4" />}
              Entrar
            </button>
          </form>
          <Link to="/" className="mt-4 block text-center text-xs text-white/40 hover:text-white/70">
            ← Voltar à loja
          </Link>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen" data-testid="admin-page">
      <div className="film-grain" />
      <div className="cinema-bg pointer-events-none fixed inset-0 opacity-60" />

      <header className="relative z-10 border-b border-violet-500/20 bg-black/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4">
          <Link
            to="/"
            className="flex items-center gap-2 rounded-full px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" /> Loja
          </Link>
          <div className="mx-auto text-center">
            <p className="text-[10px] font-semibold uppercase tracking-[0.4em] text-amber-300">
              {brand.name} — Direção
            </p>
            <h1 className="font-display text-2xl tracking-wide text-white sm:text-3xl">
              PAINEL DE PEDIDOS
            </h1>
          </div>
          <button
            data-testid="admin-new-orders-bell"
            onClick={() => setNewCount(0)}
            title="Pedidos novos desde que você abriu o painel"
            className="relative flex h-10 w-10 items-center justify-center rounded-full text-white/70 transition-colors hover:bg-white/5 hover:text-white"
          >
            {newCount > 0 && (
              <motion.span
                animate={{ scale: [1, 1.7], opacity: [0.5, 0] }}
                transition={{ duration: 1.4, repeat: Infinity }}
                className="absolute inset-1 rounded-full bg-amber-400"
              />
            )}
            <Bell className={`relative h-5 w-5 ${newCount > 0 ? "text-amber-300" : ""}`} />
            {newCount > 0 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 300 }}
                data-testid="admin-new-orders-count"
                className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-400 px-1 text-[10px] font-bold text-black shadow-lg shadow-amber-900/40"
              >
                {newCount}
              </motion.span>
            )}
          </button>
          <button
            data-testid="admin-logout-button"
            onClick={logout}
            className="flex items-center gap-2 rounded-full px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-red-300"
          >
            <LogOut className="h-4 w-4" /> Sair
          </button>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-6xl px-4 py-8">
        <div className="mb-4 flex items-center justify-between">
          <p className="text-sm text-white/50">
            {orders.length} pedido{orders.length !== 1 ? "s" : ""} • atualiza sozinho a cada 15s
            com alerta sonoro de venda nova
          </p>
          <button
            data-testid="admin-refresh-button"
            onClick={loadOrders}
            className="flex items-center gap-2 rounded-full border border-white/10 px-4 py-2 text-xs text-white/70 transition-colors hover:border-violet-500/50 hover:text-white"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loadingOrders ? "animate-spin" : ""}`} /> Atualizar
          </button>
        </div>

        {loadingOrders && orders.length === 0 ? (
          <div className="flex justify-center py-20">
            <Loader2 className="h-8 w-8 animate-spin text-violet-400" />
          </div>
        ) : orders.length === 0 ? (
          <div className="glass rounded-3xl p-12 text-center text-white/50">
            Nenhum pedido ainda. Quando um cliente finalizar a compra, ele aparece aqui.
          </div>
        ) : (
          <div data-testid="admin-orders-table" className="flex flex-col gap-3">
            {orders.map((o, idx) => {
              const st = STATUS_OPTIONS.find((s) => s.id === o.status) || STATUS_OPTIONS[0];
              return (
                <motion.div
                  key={o.order_number}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(idx * 0.05, 0.5) }}
                  data-testid={`admin-order-${o.order_number}`}
                  className="glass grid grid-cols-1 gap-4 rounded-2xl p-4 sm:grid-cols-[auto_1fr_auto_auto] sm:items-center"
                >
                  <div>
                    <p className="font-head text-sm font-600 tracking-widest text-gradient">
                      {o.order_number}
                    </p>
                    <p className="text-[11px] text-white/40">{fmtDate(o.created_at)}</p>
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm text-white">
                      {o.customer.name}{" "}
                      <span className="text-white/40">• {o.customer.phone}</span>
                    </p>
                    <p className="truncate text-xs text-white/50">
                      {o.items.reduce((a, i) => a + i.qty, 0)} item(ns) — {o.address.city}/
                      {o.address.state} — {o.shipping.label}
                    </p>
                    <p className="text-[11px] text-white/40">{o.payment_method}</p>
                  </div>
                  <p className="font-display text-2xl text-white">{formatBRL(o.total)}</p>
                  <select
                    data-testid={`admin-status-select-${o.order_number}`}
                    value={o.status}
                    onChange={(e) => changeStatus(o.order_number, e.target.value)}
                    className={`h-11 cursor-pointer rounded-xl border px-3 font-head text-xs font-600 uppercase tracking-wide outline-none transition-colors ${st.color} [&>option]:bg-[#0d0a18] [&>option]:text-white`}
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.label}
                      </option>
                    ))}
                  </select>
                </motion.div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
