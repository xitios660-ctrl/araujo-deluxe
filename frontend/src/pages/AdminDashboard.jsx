import { useCallback, useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { CalendarBlank, CurrencyDollar, Users, SignOut, LockSimple, LockSimpleOpen, CheckCircle, XCircle, Sparkle, HourglassMedium, Receipt, X } from "@phosphor-icons/react";
import { useAuth } from "../context/AuthContext";
import { WhatsAppPanel } from "../components/WhatsAppPanel";
import { api, apiError, BRL } from "../lib/api";

const todayStr = () => new Date().toLocaleDateString("sv-SE");

const STATUS_STYLE = {
  pendente: "bg-amber-100 text-amber-800",
  confirmada: "bg-emerald-100 text-emerald-800",
  concluida: "bg-stone-200 text-stone-700",
  cancelada: "bg-red-100 text-red-700",
};

export default function AdminDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [tab, setTab] = useState("agenda");
  const [date, setDate] = useState(todayStr());
  const [agenda, setAgenda] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [filter, setFilter] = useState("");
  const [proof, setProof] = useState(null);

  const viewProof = async (b) => {
    try {
      const { data } = await api.get(`/admin/proofs/${b.proof_id}`);
      setProof({ ...data, code: b.code });
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  useEffect(() => {
    if (user === false) navigate("/admin");
  }, [user, navigate]);

  const loadStats = useCallback(() => {
    api.get("/admin/stats").then((r) => setStats(r.data)).catch(() => {});
  }, []);

  const loadAgenda = useCallback(() => {
    api.get(`/admin/agenda?date=${date}`).then((r) => setAgenda(r.data)).catch(() => {});
  }, [date]);

  const loadBookings = useCallback(() => {
    api.get(`/admin/bookings${filter ? `?status=${filter}` : ""}`).then((r) => setBookings(r.data)).catch(() => {});
  }, [filter]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => { loadAgenda(); }, [loadAgenda]);
  useEffect(() => { loadBookings(); }, [loadBookings]);

  if (!user) return null;

  const refresh = () => {
    loadStats();
    loadAgenda();
    loadBookings();
  };

  const block = async (time) => {
    try {
      await api.post("/admin/blocks", { date, time, reason: "Bloqueado pela profissional" });
      toast.success(time ? `Horário ${time} bloqueado` : "Dia inteiro bloqueado");
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const unblock = async (blockId) => {
    try {
      await api.delete(`/admin/blocks/${blockId}`);
      toast.success("Horário liberado");
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  const setStatus = async (id, status) => {
    try {
      await api.patch(`/admin/bookings/${id}`, { status });
      toast.success(`Agendamento ${status === "cancelada" ? "cancelado" : status === "concluida" ? "concluído" : "confirmado"}`);
      refresh();
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  return (
    <div className="min-h-screen bg-[#F1EBDD]" data-testid="admin-dashboard">
      <header className="bg-white border-b border-border sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="font-display text-xl text-foreground">
            Araújo <span className="italic text-primary">Deluxe</span> <span className="text-muted-foreground text-xs font-sans ml-2">· painel</span>
          </Link>
          <button onClick={() => { logout(); navigate("/admin"); }} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-destructive transition-colors duration-300" data-testid="admin-logout-button">
            <SignOut size={18} /> Sair
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8 space-y-8">
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard icon={CalendarBlank} label="Hoje" value={stats?.today ?? "–"} testId="stat-today" />
          <StatCard icon={Sparkle} label="Próximos" value={stats?.upcoming ?? "–"} testId="stat-upcoming" />
          <StatCard icon={HourglassMedium} label="Sinais pendentes" value={stats?.pending ?? "–"} testId="stat-pending" />
          <StatCard icon={CurrencyDollar} label="Receita do mês" value={stats ? BRL(stats.month_revenue) : "–"} testId="stat-revenue" />
          <StatCard icon={Users} label="Clientes" value={stats?.total_clients ?? "–"} testId="stat-clients" />
        </div>

        <div className="flex gap-2">
          {[["agenda", "Agenda do dia"], ["bookings", "Todos os agendamentos"], ["whatsapp", "Bot WhatsApp"]].map(([k, label]) => (
            <button
              key={k}
              onClick={() => setTab(k)}
              className={`rounded-full px-6 py-2.5 text-sm font-semibold transition-colors duration-300 ${tab === k ? "bg-foreground text-white" : "bg-white border border-border text-foreground"}`}
              data-testid={`admin-tab-${k}`}
            >
              {label}
            </button>
          ))}
        </div>

        {tab === "agenda" && (
          <div className="bg-white rounded-3xl border border-border p-6 sm:p-8" data-testid="admin-agenda-panel">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
              <div>
                <h2 className="font-display text-2xl text-foreground">Agenda do dia</h2>
                <p className="text-muted-foreground text-sm mt-1 capitalize">{agenda?.weekday_name}</p>
              </div>
              <div className="flex items-center gap-3">
                <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded-xl border border-border px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary" data-testid="admin-agenda-date" />
                {agenda?.open && !agenda.slots.some((s) => s.reason === "bloqueado" && !s.booking) && (
                  <button onClick={() => block(null)} className="rounded-full border border-destructive/40 text-destructive text-xs font-semibold px-4 py-2.5 hover:bg-destructive/10 transition-colors duration-300" data-testid="admin-block-day-button">
                    Bloquear dia inteiro
                  </button>
                )}
              </div>
            </div>
            {agenda && !agenda.open && <p className="text-muted-foreground text-sm">Domingo — o estúdio não abre neste dia.</p>}
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {agenda?.slots.map((s) => (
                <div key={s.time} className={`rounded-2xl border p-5 ${s.booking ? "border-primary/40 bg-accent/40" : s.reason === "bloqueado" ? "border-border bg-muted" : "border-border"}`} data-testid={`admin-slot-${s.time.replace(":", "")}`}>
                  <div className="flex items-center justify-between">
                    <p className="font-display text-2xl text-foreground">{s.time}</p>
                    <SlotBadge slot={s} />
                  </div>
                  {s.booking ? (
                    <div className="mt-3 text-sm">
                      <p className="font-semibold text-foreground">{s.booking.client_name}</p>
                      <p className="text-muted-foreground text-xs mt-0.5">{s.booking.service_name} · {BRL(s.booking.price)}</p>
                      <p className="text-muted-foreground text-xs">{s.booking.client_phone}</p>
                      <div className="flex gap-2 mt-3">
                        <button onClick={() => setStatus(s.booking.id, s.booking.status === "pendente" ? "confirmada" : "concluida")} className="flex-1 rounded-full bg-foreground text-white text-xs font-semibold py-2 hover:bg-foreground/80 transition-colors duration-300" data-testid={`admin-complete-${s.time.replace(":", "")}`}>
                          {s.booking.status === "pendente" ? "Confirmar sinal" : "Concluir"}
                        </button>
                        <button onClick={() => setStatus(s.booking.id, "cancelada")} className="flex-1 rounded-full border border-destructive/40 text-destructive text-xs font-semibold py-2 hover:bg-destructive/10 transition-colors duration-300" data-testid={`admin-cancel-${s.time.replace(":", "")}`}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  ) : s.reason === "bloqueado" ? (
                    <button onClick={() => unblock(s.block_id)} className="mt-3 w-full rounded-full border border-border text-foreground text-xs font-semibold py-2 flex items-center justify-center gap-1.5 hover:border-primary transition-colors duration-300" data-testid={`admin-unblock-${s.time.replace(":", "")}`}>
                      <LockSimpleOpen size={14} /> Liberar horário
                    </button>
                  ) : s.reason === "passado" ? (
                    <p className="text-muted-foreground text-xs mt-3">Horário já passou</p>
                  ) : (
                    <button onClick={() => block(s.time)} className="mt-3 w-full rounded-full border border-border text-muted-foreground text-xs font-semibold py-2 flex items-center justify-center gap-1.5 hover:border-destructive hover:text-destructive transition-colors duration-300" data-testid={`admin-block-${s.time.replace(":", "")}`}>
                      <LockSimple size={14} /> Bloquear
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "bookings" && (
          <div className="bg-white rounded-3xl border border-border p-6 sm:p-8" data-testid="admin-bookings-panel">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
              <h2 className="font-display text-2xl text-foreground">Todos os agendamentos</h2>
              <select value={filter} onChange={(e) => setFilter(e.target.value)} className="rounded-xl border border-border px-4 py-2.5 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-primary" data-testid="admin-filter-status">
                <option value="">Todos</option>
                <option value="pendente">Sinal pendente</option>
                <option value="confirmada">Confirmadas</option>
                <option value="concluida">Concluídas</option>
                <option value="cancelada">Canceladas</option>
              </select>
            </div>
            {bookings.length === 0 && <p className="text-muted-foreground text-sm py-8 text-center">Nenhum agendamento encontrado.</p>}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-muted-foreground text-xs uppercase tracking-wider border-b border-border">
                    <th className="py-3 pr-4">Data</th>
                    <th className="py-3 pr-4">Hora</th>
                    <th className="py-3 pr-4">Cliente</th>
                    <th className="py-3 pr-4">Serviço</th>
                    <th className="py-3 pr-4">Valor</th>
                    <th className="py-3 pr-4">Status</th>
                    <th className="py-3">Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {bookings.map((b) => (
                    <tr key={b.id} className="border-b border-border/60 hover:bg-muted/40 transition-colors duration-200" data-testid={`admin-booking-row-${b.code}`}>
                      <td className="py-3.5 pr-4 whitespace-nowrap">{b.date.split("-").reverse().join("/")}</td>
                      <td className="py-3.5 pr-4">{b.time}</td>
                      <td className="py-3.5 pr-4">
                        <p className="font-medium text-foreground">{b.client_name}</p>
                        <p className="text-muted-foreground text-xs">{b.client_phone}</p>
                      </td>
                      <td className="py-3.5 pr-4">{b.service_name}</td>
                      <td className="py-3.5 pr-4 whitespace-nowrap">{BRL(b.price)}</td>
                      <td className="py-3.5 pr-4">
                        <div className="flex items-center gap-2">
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_STYLE[b.status]}`}>{b.status}</span>
                          {b.proof_id && (
                            <button onClick={() => viewProof(b)} title="Ver comprovante" className="text-primary hover:scale-110 transition-transform duration-200" data-testid={`admin-proof-${b.code}`}>
                              <Receipt size={19} weight="duotone" />
                            </button>
                          )}
                        </div>
                      </td>
                      <td className="py-3.5">
                        {(b.status === "confirmada" || b.status === "pendente") && (
                          <div className="flex gap-2">
                            <button onClick={() => setStatus(b.id, b.status === "pendente" ? "confirmada" : "concluida")} title={b.status === "pendente" ? "Confirmar sinal recebido" : "Concluir"} className="text-emerald-600 hover:scale-110 transition-transform duration-200" data-testid={`admin-row-complete-${b.code}`}>
                              <CheckCircle size={20} weight="fill" />
                            </button>
                            <button onClick={() => setStatus(b.id, "cancelada")} title="Cancelar" className="text-red-500 hover:scale-110 transition-transform duration-200" data-testid={`admin-row-cancel-${b.code}`}>
                              <XCircle size={20} weight="fill" />
                            </button>
                          </div>
                        )}
                        {b.status === "cancelada" && (
                          <button onClick={() => setStatus(b.id, "confirmada")} className="text-xs text-primary font-semibold hover:underline" data-testid={`admin-row-restore-${b.code}`}>
                            Reativar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
        {tab === "whatsapp" && <WhatsAppPanel />}
      </main>

      {proof && (
        <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-6" onClick={() => setProof(null)} data-testid="admin-proof-modal">
          <div className="bg-white rounded-3xl p-6 max-w-2xl w-full max-h-[85vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <p className="font-display text-xl text-foreground">Comprovante · {proof.code}</p>
              <button onClick={() => setProof(null)} className="text-muted-foreground hover:text-foreground" data-testid="admin-proof-close">
                <X size={22} />
              </button>
            </div>
            {proof.mime === "application/pdf" ? (
              <embed src={`data:application/pdf;base64,${proof.data}`} type="application/pdf" className="w-full h-[65vh] rounded-xl" />
            ) : (
              <img src={`data:${proof.mime};base64,${proof.data}`} alt="Comprovante" className="w-full rounded-xl" data-testid="admin-proof-image" />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const StatCard = ({ icon: Icon, label, value, testId }) => (
  <div className="bg-white rounded-3xl border border-border p-6 shadow-[0_1px_2px_rgba(42,31,29,0.05)]" data-testid={testId}>
    <Icon size={22} className="text-primary" weight="duotone" />
    <p className="font-display text-3xl text-foreground mt-3">{value}</p>
    <p className="text-muted-foreground text-xs mt-1 uppercase tracking-wider">{label}</p>
  </div>
);

const SlotBadge = ({ slot }) => {
  if (slot.booking) {
    if (slot.booking.status === "pendente") return <span className="rounded-full bg-amber-100 text-amber-800 text-xs font-semibold px-3 py-1">sinal pendente</span>;
    return <span className="rounded-full bg-primary/15 text-primary text-xs font-semibold px-3 py-1">agendado</span>;
  }
  if (slot.reason === "bloqueado") return <span className="rounded-full bg-stone-200 text-stone-600 text-xs font-semibold px-3 py-1">bloqueado</span>;
  if (slot.reason === "passado") return <span className="rounded-full bg-muted text-muted-foreground text-xs font-semibold px-3 py-1">passado</span>;
  return <span className="rounded-full bg-emerald-100 text-emerald-700 text-xs font-semibold px-3 py-1">livre</span>;
};
