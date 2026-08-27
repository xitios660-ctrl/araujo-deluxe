import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ptBR } from "date-fns/locale";
import { format } from "date-fns";
import { toast } from "sonner";
import { CheckCircle, CaretLeft, SealCheck, CalendarBlank, Clock, User, CopySimple, PixLogo, UploadSimple, WhatsappLogo } from "@phosphor-icons/react";
import { Calendar } from "../components/ui/calendar";
import { api, apiError, BRL, CATEGORY_LABELS } from "../lib/api";

const STEPS = ["Serviço", "Data", "Horário", "Seus dados", "Confirmado"];

const slide = {
  initial: { opacity: 0, x: 60, rotateY: 6 },
  animate: { opacity: 1, x: 0, rotateY: 0, transition: { duration: 0.55, ease: [0.22, 1, 0.36, 1] } },
  exit: { opacity: 0, x: -60, rotateY: -6, transition: { duration: 0.35 } },
};

export const BookingSection = ({ preselected }) => {
  const [step, setStep] = useState(0);
  const [services, setServices] = useState([]);
  const [service, setService] = useState(null);
  const [date, setDate] = useState(null);
  const [availability, setAvailability] = useState(null);
  const [time, setTime] = useState(null);
  const [form, setForm] = useState({ client_name: "", client_phone: "", notes: "" });
  const [booking, setBooking] = useState(null);
  const [loading, setLoading] = useState(false);
  const [proofUploading, setProofUploading] = useState(false);

  const uploadProof = async (file) => {
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) return toast.error("Arquivo muito grande (máx 8MB)");
    setProofUploading(true);
    try {
      const b64 = await new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(",")[1]);
        r.onerror = rej;
        r.readAsDataURL(file);
      });
      await api.post(`/bookings/${booking.id}/proof`, { data_base64: b64, mime: file.type || "image/jpeg" });
      setBooking((b) => ({ ...b, status: "confirmada", proof_uploaded: true }));
      toast.success("Comprovante enviado! Horário confirmado ✨");
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setProofUploading(false);
    }
  };

  useEffect(() => {
    api.get("/services").then((r) => setServices(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    if (preselected) {
      setService(preselected);
      setStep(1);
      setDate(null);
      setTime(null);
      setBooking(null);
    }
  }, [preselected]);

  useEffect(() => {
    if (!date) return;
    const d = format(date, "yyyy-MM-dd");
    setAvailability(null);
    setTime(null);
    api.get(`/availability?date=${d}`).then((r) => setAvailability(r.data)).catch(() => toast.error("Erro ao consultar horários"));
  }, [date]);

  const grouped = useMemo(() => {
    const g = {};
    services.forEach((s) => {
      (g[s.category] = g[s.category] || []).push(s);
    });
    return g;
  }, [services]);

  const submit = async () => {
    if (form.client_name.trim().length < 2) return toast.error("Informe seu nome completo");
    if (form.client_phone.replace(/\D/g, "").length < 8) return toast.error("Informe um WhatsApp válido");
    setLoading(true);
    try {
      const { data } = await api.post("/bookings", {
        service_id: service.id,
        date: format(date, "yyyy-MM-dd"),
        time,
        ...form,
      });
      setBooking(data);
      setStep(4);
      toast.success(data.status === "pendente" ? "Reserva criada! Pague o sinal para confirmar." : "Agendamento confirmado!");
    } catch (e) {
      toast.error(apiError(e));
      if (e?.response?.status === 409) {
        const d = format(date, "yyyy-MM-dd");
        api.get(`/availability?date=${d}`).then((r) => setAvailability(r.data));
        setStep(2);
      }
    } finally {
      setLoading(false);
    }
  };

  const waLink = () => {
    const dateFmt = format(new Date(booking.date + "T12:00:00"), "dd/MM/yyyy");
    const msg = booking.payment
      ? `Olá! Fiz uma reserva no Araújo Deluxe ✨\n\nServiço: ${booking.service_name}\nData: ${dateFmt} às ${booking.time}\nCódigo: ${booking.code}\n\nSegue o comprovante do sinal de R$ ${booking.payment.amount} via PIX.`
      : `Olá! Acabei de agendar no Araújo Deluxe ✨\n\nServiço: ${booking.service_name}\nData: ${dateFmt} às ${booking.time}\nCódigo: ${booking.code}`;
    return `https://wa.me/${booking.whatsapp}?text=${encodeURIComponent(msg)}`;
  };

  const copyPix = () => {
    navigator.clipboard.writeText(booking.payment.pix_code);
    toast.success("Código PIX copiado!");
  };

  const reset = () => {
    setStep(0);
    setService(null);
    setDate(null);
    setTime(null);
    setForm({ client_name: "", client_phone: "", notes: "" });
    setBooking(null);
  };

  return (
    <section id="agendar" className="bg-[#221A0E] relative grain py-24 lg:py-32" data-testid="booking-section">
      <div className="max-w-5xl mx-auto px-6 lg:px-10 relative z-10">
        <div className="mb-12">
          <p className="text-primary uppercase tracking-[0.3em] text-xs font-semibold mb-4">Agendamento inteligente</p>
          <h2 className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-tight text-white">
            Reserve seu <em className="italic text-primary">momento</em>
          </h2>
          <p className="text-white/60 mt-4 max-w-xl leading-relaxed text-sm md:text-base">
            Atendemos de segunda a sexta às 9h, 11h, 15h30 e 17h · sábados às 9h, 11h, 14h, 16h e 18h. O sistema mostra apenas horários realmente disponíveis.
          </p>
        </div>

        <div className="flex items-center gap-2 mb-10 flex-wrap" data-testid="booking-steps">
          {STEPS.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`flex items-center gap-2 rounded-full px-4 py-2 text-xs font-semibold transition-colors duration-300 ${
                  i === step ? "bg-primary text-white" : i < step ? "bg-white/15 text-white" : "bg-white/5 text-white/40"
                }`}
              >
                <span>{i < step ? <CheckCircle size={14} weight="fill" /> : i + 1}</span> {s}
              </div>
              {i < STEPS.length - 1 && <div className="w-4 h-px bg-white/20 hidden sm:block" />}
            </div>
          ))}
        </div>

        <div className="glass-dark rounded-[2rem] p-6 sm:p-10 min-h-[420px] perspective-wrap">
          <AnimatePresence mode="wait">
            {step === 0 && (
              <motion.div key="s0" {...slide}>
                <h3 className="font-display text-2xl text-white mb-6">Escolha o serviço</h3>
                <div className="space-y-8">
                  {Object.entries(grouped).map(([c, list]) => (
                    <div key={c}>
                      <p className="text-primary uppercase tracking-[0.25em] text-xs font-semibold mb-3">{CATEGORY_LABELS[c]}</p>
                      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                        {list.map((s) => (
                          <button
                            key={s.id}
                            onClick={() => {
                              setService(s);
                              setStep(1);
                            }}
                            className={`text-left rounded-2xl border p-4 transition-colors duration-300 ${
                              service?.id === s.id ? "border-primary bg-primary/15" : "border-white/15 hover:border-primary/60 bg-white/5"
                            }`}
                            data-testid={`booking-service-${s.id}`}
                          >
                            <div className="flex justify-between items-start gap-2">
                              <p className="text-white text-sm font-semibold leading-snug">{s.name}</p>
                              <p className="text-primary font-display">{BRL(s.price)}</p>
                            </div>
                            <p className="text-white/50 text-xs mt-1.5">{s.duration}{s.deposit > 0 ? ` · sinal ${BRL(s.deposit)}` : ""}</p>
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}

            {step === 1 && (
              <motion.div key="s1" {...slide}>
                <StepHeader onBack={() => setStep(0)} title="Escolha o dia" subtitle={service?.name} />
                <div className="flex justify-center">
                  <div className="bg-white rounded-3xl p-4 sm:p-6" data-testid="booking-calendar">
                    <Calendar
                      mode="single"
                      selected={date}
                      onSelect={(d) => {
                        if (!d) return;
                        setDate(d);
                        setStep(2);
                      }}
                      locale={ptBR}
                      disabled={[{ dayOfWeek: [0] }, { before: new Date() }]}
                      className="pointer-events-auto"
                    />
                  </div>
                </div>
                <p className="text-white/40 text-xs text-center mt-4">Domingos o estúdio não abre — eles já aparecem desativados.</p>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div key="s2" {...slide}>
                <StepHeader
                  onBack={() => setStep(1)}
                  title="Escolha o horário"
                  subtitle={date ? `${availability?.weekday_name || ""}, ${format(date, "dd 'de' MMMM", { locale: ptBR })}` : ""}
                />
                {!availability && <p className="text-white/50 text-sm">Consultando a agenda…</p>}
                {availability && !availability.open && <p className="text-white/70">Não atendemos neste dia. Volte e escolha outra data.</p>}
                {availability?.open && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 max-w-2xl" data-testid="booking-slots">
                    {availability.slots.map((s) => (
                      <button
                        key={s.time}
                        disabled={!s.available}
                        onClick={() => {
                          setTime(s.time);
                          setStep(3);
                        }}
                        className={`rounded-2xl py-5 font-display text-xl transition-[transform,background-color] duration-300 ${
                          s.available
                            ? "bg-white/10 border border-white/20 text-white hover:bg-primary hover:scale-105"
                            : "bg-white/5 border border-white/5 text-white/25 line-through cursor-not-allowed"
                        }`}
                        data-testid={`booking-slot-${s.time.replace(":", "")}`}
                      >
                        {s.time}
                      </button>
                    ))}
                  </div>
                )}
                {availability?.open && availability.slots.every((s) => !s.available) && (
                  <p className="text-white/60 text-sm mt-6">Todos os horários deste dia já foram reservados. Escolha outra data. ✨</p>
                )}
              </motion.div>
            )}

            {step === 3 && (
              <motion.div key="s3" {...slide}>
                <StepHeader onBack={() => setStep(2)} title="Quase lá! Seus dados" subtitle={`${service?.name} · ${date && format(date, "dd/MM")} às ${time}`} />
                <div className="grid sm:grid-cols-2 gap-4 max-w-2xl">
                  <input
                    value={form.client_name}
                    onChange={(e) => setForm({ ...form, client_name: e.target.value })}
                    placeholder="Nome completo"
                    className="rounded-xl bg-white/10 border border-white/20 text-white placeholder:text-white/40 px-5 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    data-testid="booking-input-name"
                  />
                  <input
                    value={form.client_phone}
                    onChange={(e) => setForm({ ...form, client_phone: e.target.value })}
                    placeholder="WhatsApp (com DDD)"
                    className="rounded-xl bg-white/10 border border-white/20 text-white placeholder:text-white/40 px-5 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                    data-testid="booking-input-phone"
                  />
                  <textarea
                    value={form.notes}
                    onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    placeholder="Observações (opcional)"
                    rows={3}
                    className="sm:col-span-2 rounded-xl bg-white/10 border border-white/20 text-white placeholder:text-white/40 px-5 py-4 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                    data-testid="booking-input-notes"
                  />
                </div>
                <div className="flex items-center justify-between flex-wrap gap-4 mt-8 max-w-2xl">
                  <div className="text-white/70 text-sm">
                    <p>
                      Total: <span className="font-display text-xl text-primary">{BRL(service?.price || 0)}</span>
                      {service?.deposit > 0 && <span className="text-white/50"> · sinal de {BRL(service.deposit)} para reservar</span>}
                    </p>
                  </div>
                  <button
                    onClick={submit}
                    disabled={loading}
                    className="rounded-full bg-primary text-white font-semibold px-10 py-4 transition-transform duration-300 hover:scale-105 hover:bg-[#a3822b] disabled:opacity-50"
                    data-testid="booking-submit-button"
                  >
                    {loading ? "Confirmando…" : "Confirmar agendamento"}
                  </button>
                </div>
              </motion.div>
            )}

            {step === 4 && booking && (
              <motion.div key="s4" {...slide} className="text-center py-6">
                <motion.div initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 200, damping: 14, delay: 0.15 }}>
                  <SealCheck size={72} weight="fill" className={booking.status === "pendente" ? "text-amber-400 mx-auto" : "text-primary mx-auto"} />
                </motion.div>
                <h3 className="font-display text-3xl sm:text-4xl text-white mt-6">{booking.status === "pendente" ? "Falta só o sinal!" : "Horário confirmado!"}</h3>
                <p className="text-white/60 mt-2 text-sm">Código do agendamento: <span className="text-primary font-semibold">{booking.code}</span></p>
                <div className={`grid gap-6 mx-auto mt-8 text-left ${booking.payment ? "md:grid-cols-2 max-w-3xl items-start" : "max-w-md"}`}>
                  <div className="glass-dark rounded-3xl p-8 space-y-4" data-testid="booking-confirmation-card">
                    <Row icon={<User size={18} />} label="Cliente" value={booking.client_name} />
                    <Row icon={<SealCheck size={18} />} label="Serviço" value={`${booking.service_name} · ${BRL(booking.price)}`} />
                    <Row icon={<CalendarBlank size={18} />} label="Data" value={format(new Date(booking.date + "T12:00:00"), "EEEE, dd 'de' MMMM", { locale: ptBR })} />
                    <Row icon={<Clock size={18} />} label="Horário" value={booking.time} />
                  </div>
                  {booking.payment && (
                    <div className="bg-white rounded-3xl p-8" data-testid="booking-pix-panel">
                      {booking.status === "pendente" ? (
                        <>
                          <p className="flex items-center gap-2 text-foreground font-semibold text-sm">
                            <PixLogo size={22} className="text-emerald-600" /> Pague o sinal de {BRL(booking.payment.amount)} via PIX
                          </p>
                          <p className="text-muted-foreground text-xs mt-2 leading-relaxed">
                            Envie o comprovante <strong>aqui pelo site</strong> — seu horário é confirmado na hora e você recebe a confirmação no WhatsApp.
                          </p>
                          <img
                            src={`data:image/png;base64,${booking.payment.qr_base64}`}
                            alt="QR Code PIX"
                            className="w-40 h-40 mx-auto my-5 rounded-xl border border-border"
                            data-testid="booking-pix-qr"
                          />
                          <button
                            onClick={copyPix}
                            className="w-full rounded-full border border-border text-foreground text-xs font-semibold py-3 flex items-center justify-center gap-2 hover:border-primary transition-colors duration-300"
                            data-testid="booking-pix-copy"
                          >
                            <CopySimple size={15} /> Copiar código PIX (copia e cola)
                          </button>
                          <label
                            className={`mt-3 w-full rounded-full bg-primary text-white text-sm font-semibold py-3.5 flex items-center justify-center gap-2 cursor-pointer transition-transform duration-300 hover:scale-[1.02] hover:bg-[#a3822b] ${proofUploading ? "opacity-60 pointer-events-none" : ""}`}
                            data-testid="booking-proof-upload-label"
                          >
                            <UploadSimple size={19} weight="bold" />
                            {proofUploading ? "Enviando comprovante…" : "Enviar comprovante (foto ou PDF)"}
                            <input
                              type="file"
                              accept="image/*,application/pdf"
                              className="hidden"
                              disabled={proofUploading}
                              onChange={(e) => uploadProof(e.target.files?.[0])}
                              data-testid="booking-proof-input"
                            />
                          </label>
                        </>
                      ) : (
                        <div className="text-center py-4" data-testid="booking-proof-confirmed">
                          <SealCheck size={44} weight="fill" className="text-emerald-500 mx-auto" />
                          <p className="text-foreground font-semibold text-sm mt-3">Comprovante recebido!</p>
                          <p className="text-muted-foreground text-xs mt-2 leading-relaxed">
                            Seu horário está confirmado. A confirmação chega no seu WhatsApp em instantes. 💛
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
                {!booking.payment && !booking.proof_uploaded && (
                  <a
                    href={waLink()}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex mt-6 rounded-full bg-[#25D366] text-white text-sm font-semibold px-8 py-3.5 items-center gap-2 transition-transform duration-300 hover:scale-105"
                    data-testid="booking-whatsapp-button"
                  >
                    <WhatsappLogo size={19} weight="fill" /> Avisar no WhatsApp
                  </a>
                )}
                <div>
                  <button onClick={reset} className="mt-8 rounded-full border border-white/30 text-white px-8 py-3 text-sm font-medium transition-colors duration-300 hover:bg-white/10" data-testid="booking-new-button">
                    Fazer novo agendamento
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
};

const StepHeader = ({ onBack, title, subtitle }) => (
  <div className="mb-8">
    <button onClick={onBack} className="text-white/50 text-xs flex items-center gap-1 mb-3 hover:text-primary transition-colors duration-300" data-testid="booking-back-button">
      <CaretLeft size={13} /> voltar
    </button>
    <h3 className="font-display text-2xl text-white">{title}</h3>
    {subtitle && <p className="text-primary text-sm mt-1 capitalize">{subtitle}</p>}
  </div>
);

const Row = ({ icon, label, value }) => (
  <div className="flex items-center gap-4">
    <span className="text-primary">{icon}</span>
    <div>
      <p className="text-white/40 text-xs uppercase tracking-widest">{label}</p>
      <p className="text-white text-sm font-medium capitalize">{value}</p>
    </div>
  </div>
);
