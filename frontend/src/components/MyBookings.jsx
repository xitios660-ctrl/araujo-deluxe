import { useState } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { MagnifyingGlass, CalendarBlank, Clock } from "@phosphor-icons/react";
import { api, apiError, BRL } from "../lib/api";

const STATUS_BADGE = {
  pendente: ["Sinal pendente", "bg-amber-100 text-amber-800"],
  confirmada: ["Confirmada", "bg-emerald-100 text-emerald-800"],
  concluida: ["Concluída", "bg-stone-200 text-stone-700"],
  cancelada: ["Cancelada", "bg-red-100 text-red-700"],
};

const bookingBadge = (booking) => {
  if (booking.status === "pendente" && booking.proof_status === "em_analise") return ["Comprovante em análise", "bg-sky-100 text-sky-800"];
  if (booking.status === "pendente" && booking.proof_status === "rejeitado") return ["Comprovante não aprovado", "bg-red-100 text-red-700"];
  return STATUS_BADGE[booking.status] || [booking.status, "bg-muted"];
};

const PROOF_ACCEPT = "image/jpeg,image/png,image/webp,image/heic,image/heif,application/pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,.pdf";
const PROOF_TYPES = new Set(["image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"]);

const validProofFile = (file) => {
  if (!file) return false;
  if (file.size > 8 * 1024 * 1024) {
    toast.error("Arquivo muito grande (máx. 8 MB)");
    return false;
  }
  const type = (file.type || "").toLowerCase();
  const extension = (file.name || "").split(".").pop()?.toLowerCase();
  const validExtension = ["jpg", "jpeg", "png", "webp", "heic", "heif", "pdf"].includes(extension);
  if (!PROOF_TYPES.has(type) && !validExtension) {
    toast.error("Envie o comprovante em JPG, PNG, WEBP, HEIC ou PDF");
    return false;
  }
  return true;
};

export const MyBookings = () => {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [cancelId, setCancelId] = useState(null);
  const [cancelPhone, setCancelPhone] = useState("");
  const [uploadingId, setUploadingId] = useState(null);

  const uploadProof = async (id, file) => {
    if (!validProofFile(file)) return;
    setUploadingId(id);
    try {
      const b64 = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(",")[1]);
        r.onerror = rej;
        r.readAsDataURL(file);
      });
      await api.post(`/bookings/${id}/proof`, { data_base64: b64, mime: file.type || "image/jpeg" });
      toast.success("Comprovante enviado! Agora ele está sendo analisado ✨");
      search();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setUploadingId(null);
    }
  };

  const search = async (e) => {
    e?.preventDefault();
    if (query.trim().length < 4) return toast.error("Informe o código (AD-XXXXXX) ou seu telefone com DDD");
    setLoading(true);
    setCancelId(null);
    try {
      const { data } = await api.get(`/bookings/lookup?q=${encodeURIComponent(query.trim())}`);
      setResults(data);
      if (data.length === 0) toast.info("Nenhum agendamento encontrado");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  const cancel = async (id) => {
    const phone = cancelPhone || query;
    if (phone.replace(/\D/g, "").length < 8) return toast.error("Confirme seu telefone com DDD");
    try {
      await api.post(`/bookings/${id}/cancel`, { phone });
      toast.success("Agendamento cancelado");
      setCancelId(null);
      setCancelPhone("");
      search();
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  const cancellable = (b) => ["pendente", "confirmada"].includes(b.status);

  return (
    <section id="consultar" className="max-w-4xl mx-auto px-6 lg:px-10 py-24" data-testid="mybookings-section">
      <p className="text-primary uppercase tracking-[0.3em] text-xs font-semibold mb-4">Minha reserva</p>
      <h2 className="font-display text-4xl sm:text-5xl tracking-tight text-foreground">
        Consulte seu <em className="italic text-primary">agendamento</em>
      </h2>
      <p className="text-muted-foreground text-sm mt-4 max-w-lg leading-relaxed">
        Digite o código da reserva (ex: AD-1A2B3C) ou o telefone usado no agendamento para ver ou cancelar seu horário.
      </p>
      <form onSubmit={search} className="flex flex-col sm:flex-row gap-3 mt-8 max-w-xl">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Código ou telefone com DDD"
          className="flex-1 rounded-full bg-white border border-border px-6 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          data-testid="mybookings-search-input"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-foreground text-white font-semibold px-8 py-4 text-sm flex items-center justify-center gap-2 transition-transform duration-300 hover:scale-105 disabled:opacity-50"
          data-testid="mybookings-search-button"
        >
          <MagnifyingGlass size={17} /> {loading ? "Buscando…" : "Buscar"}
        </button>
      </form>

      {results && results.length > 0 && (
        <div className="mt-10 space-y-4" data-testid="mybookings-results">
          {results.map((b, i) => {
            const [label, style] = bookingBadge(b);
            return (
              <motion.div
                key={b.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06, duration: 0.5 }}
                className="bg-white border border-border rounded-3xl p-6 sm:p-7"
                data-testid={`mybookings-card-${b.code}`}
              >
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-3 flex-wrap">
                      <h3 className="font-display text-xl text-foreground">{b.service_name}</h3>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${style}`}>{label}</span>
                    </div>
                    <div className="flex items-center gap-5 mt-3 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <CalendarBlank size={15} /> {b.date.split("-").reverse().join("/")}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Clock size={15} /> {b.time}
                      </span>
                      <span>{BRL(b.price)}</span>
                    </div>
                    <p className="text-muted-foreground/70 text-xs mt-2">Código: {b.code}</p>
                  </div>
                  {cancellable(b) && (
                    <div className="text-right">
                      {cancelId === b.id ? (
                        <div className="flex flex-col gap-2 items-end">
                          <input
                            value={cancelPhone}
                            onChange={(e) => setCancelPhone(e.target.value)}
                            placeholder="Confirme seu telefone"
                            className="rounded-full border border-border px-4 py-2 text-xs w-48 focus:outline-none focus:ring-2 focus:ring-primary"
                            data-testid={`mybookings-cancel-phone-${b.code}`}
                          />
                          <div className="flex gap-2">
                            <button onClick={() => cancel(b.id)} className="rounded-full bg-destructive text-white text-xs font-semibold px-4 py-2" data-testid={`mybookings-cancel-confirm-${b.code}`}>
                              Confirmar cancelamento
                            </button>
                            <button onClick={() => setCancelId(null)} className="rounded-full border border-border text-xs px-4 py-2">
                              Voltar
                            </button>
                          </div>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setCancelId(b.id);
                            setCancelPhone(query.replace(/\D/g, "").length >= 8 ? query : "");
                          }}
                          className="rounded-full border border-destructive/40 text-destructive text-xs font-semibold px-5 py-2.5 hover:bg-destructive/10 transition-colors duration-300"
                          data-testid={`mybookings-cancel-${b.code}`}
                        >
                          Cancelar horário
                        </button>
                      )}
                    </div>
                  )}
                </div>
                {b.status === "pendente" && b.proof_status === "em_analise" && (
                  <div className="text-sky-800 bg-sky-50 rounded-xl px-4 py-3 text-xs mt-4">
                    <strong>Comprovante em análise.</strong> Assim que ele for aprovado ou não aprovado, você receberá a resposta no WhatsApp.
                  </div>
                )}
                {b.status === "pendente" && b.proof_status === "rejeitado" && (
                  <div className="text-red-700 bg-red-50 rounded-xl px-4 py-2.5 text-xs mt-4 flex flex-wrap items-center justify-between gap-3">
                    <span>O comprovante não foi aprovado. Confira o pagamento e envie um novo comprovante.</span>
                    <label className={`rounded-full bg-primary text-white font-semibold px-4 py-2 cursor-pointer ${uploadingId === b.id ? "opacity-60 pointer-events-none" : ""}`} data-testid={`mybookings-proof-${b.code}`}>
                      {uploadingId === b.id ? "Enviando…" : "Enviar novo comprovante"}
                      <input type="file" accept={PROOF_ACCEPT} className="hidden" onChange={(e) => uploadProof(b.id, e.target.files?.[0])} />
                    </label>
                  </div>
                )}
                {b.status === "pendente" && !["em_analise", "rejeitado"].includes(b.proof_status) && (
                  <div className="text-amber-700 bg-amber-50 rounded-xl px-4 py-2.5 text-xs mt-4 flex flex-wrap items-center justify-between gap-3">
                    <span>Aguardando o sinal via PIX. Envie o comprovante aqui para análise.</span>
                    <label className={`rounded-full bg-primary text-white font-semibold px-4 py-2 cursor-pointer ${uploadingId === b.id ? "opacity-60 pointer-events-none" : ""}`} data-testid={`mybookings-proof-${b.code}`}>
                      {uploadingId === b.id ? "Enviando…" : "Enviar comprovante"}
                      <input type="file" accept={PROOF_ACCEPT} className="hidden" onChange={(e) => uploadProof(b.id, e.target.files?.[0])} />
                    </label>
                  </div>
                )}
              </motion.div>
            );
          })}
        </div>
      )}
      {results && results.length === 0 && (
        <p className="text-muted-foreground text-sm mt-10" data-testid="mybookings-empty">
          Nenhum agendamento encontrado com esse código ou telefone.
        </p>
      )}
    </section>
  );
};
