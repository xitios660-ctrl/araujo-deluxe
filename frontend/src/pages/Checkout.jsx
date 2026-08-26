import React, { useEffect, useState } from "react";
import axios from "axios";
import { Link, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  ArrowLeft,
  CreditCard,
  Loader2,
  MapPin,
  MessageCircle,
  Send,
  ShoppingBag,
  User,
  Zap,
} from "lucide-react";
import { brand, formatBRL } from "../mock";
import { useCart } from "../context/CartContext";
import { maskCep } from "../components/ShippingCalculator";
import { orderWhatsAppUrl } from "../lib/whatsapp";

const API = process.env.REACT_APP_BACKEND_URL;

const PAYMENTS = [
  { id: "pix", label: "PIX", desc: "Pagamento instantâneo. Chave enviada no WhatsApp.", icon: Zap },
  { id: "cartao", label: "Cartão de crédito", desc: "Em até 12x. Link de pagamento no WhatsApp.", icon: CreditCard },
  { id: "combinar", label: "Combinar no WhatsApp", desc: "Fale com a equipe e escolha a melhor forma.", icon: MessageCircle },
];

const PAYMENT_LABELS = {
  pix: "PIX",
  cartao: "Cartão de crédito (até 12x)",
  combinar: "Combinar no WhatsApp",
};

const maskPhone = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 11);
  if (d.length <= 2) return d;
  if (d.length <= 7) return `(${d.slice(0, 2)}) ${d.slice(2)}`;
  return `(${d.slice(0, 2)}) ${d.slice(2, 7)}-${d.slice(7)}`;
};

const inputCls =
  "h-12 w-full rounded-xl border border-white/10 bg-white/5 px-4 text-sm text-white placeholder:text-white/30 focus:border-violet-500/60 focus:outline-none focus:ring-2 focus:ring-violet-600/30";

function Scene({ num, title, icon: Icon, children }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: num * 0.08, duration: 0.5 }}
      className="glass rounded-3xl p-6 sm:p-7"
    >
      <div className="mb-5 flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-800 shadow-lg shadow-violet-900/40">
          <Icon className="h-5 w-5 text-white" />
        </span>
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.35em] text-amber-300">
            Cena 0{num}
          </p>
          <h2 className="font-head text-lg font-600 uppercase tracking-wide text-white">
            {title}
          </h2>
        </div>
      </div>
      {children}
    </motion.section>
  );
}

export default function Checkout() {
  const { items, subtotal, clear } = useCart();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");

  const [cep, setCep] = useState("");
  const [cepLoading, setCepLoading] = useState(false);
  const [cepError, setCepError] = useState("");
  const [shippingData, setShippingData] = useState(null);
  const [street, setStreet] = useState("");
  const [number, setNumber] = useState("");
  const [complement, setComplement] = useState("");
  const [neighborhood, setNeighborhood] = useState("");
  const [city, setCity] = useState("");
  const [uf, setUf] = useState("");
  const [shippingSel, setShippingSel] = useState(null);

  const [payment, setPayment] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const cepDigits = cep.replace(/\D/g, "");
  const total = subtotal + (shippingSel ? shippingSel.price : 0);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  useEffect(() => {
    if (cepDigits.length !== 8) {
      setShippingData(null);
      setShippingSel(null);
      setCepError("");
      return;
    }
    let active = true;
    setCepLoading(true);
    setCepError("");
    axios
      .get(`${API}/api/shipping/${cepDigits}`, { params: { subtotal } })
      .then((r) => {
        if (!active) return;
        setShippingData(r.data);
        setStreet(r.data.address.street);
        setNeighborhood(r.data.address.neighborhood);
        setCity(r.data.address.city);
        setUf(r.data.address.state);
        setShippingSel(null);
      })
      .catch((e) => {
        if (!active) return;
        setShippingData(null);
        setShippingSel(null);
        setCepError(e?.response?.data?.detail || "CEP não encontrado.");
      })
      .finally(() => active && setCepLoading(false));
    return () => {
      active = false;
    };
  }, [cepDigits, subtotal]);

  const submit = async () => {
    if (name.trim().length < 3) return toast.error("Informe seu nome completo.");
    if (phone.replace(/\D/g, "").length < 10) return toast.error("Informe um telefone/WhatsApp válido.");
    if (!shippingData) return toast.error("Informe um CEP válido para calcular o frete.");
    if (!number.trim()) return toast.error("Informe o número do endereço.");
    if (!shippingSel) return toast.error("Escolha uma opção de frete.");
    if (!payment) return toast.error("Escolha a forma de pagamento.");

    setSubmitting(true);
    try {
      const res = await axios.post(`${API}/api/orders`, {
        customer: { name: name.trim(), phone, email: email.trim() },
        address: {
          cep: maskCep(cep),
          street,
          number,
          complement,
          neighborhood,
          city,
          state: uf,
        },
        items: items.map(({ id, name: n, price, qty, image }) => ({
          id,
          name: n,
          price,
          qty,
          image,
        })),
        shipping: shippingSel,
        payment_method: PAYMENT_LABELS[payment],
        subtotal,
      });
      const order = res.data;
      window.open(orderWhatsAppUrl(order), "_blank");
      clear();
      navigate(`/pedido/${order.order_number}`, { state: { order } });
    } catch (e) {
      toast.error("Não foi possível registrar o pedido. Tente novamente.");
      setSubmitting(false);
    }
  };

  if (items.length === 0) {
    return (
      <div className="relative flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <div className="film-grain" />
        <div className="mb-5 flex h-24 w-24 items-center justify-center rounded-full bg-violet-600/10">
          <ShoppingBag className="h-10 w-10 text-violet-400/60" />
        </div>
        <h1 className="font-display text-4xl text-white sm:text-5xl">Carrinho vazio</h1>
        <p className="mt-3 max-w-md text-sm text-white/50">
          Sua cena final precisa de um elenco. Escolha suas linhas e volte para o checkout.
        </p>
        <Link
          to="/"
          data-testid="checkout-back-to-store"
          className="mt-7 rounded-full bg-gradient-to-r from-violet-600 to-purple-500 px-8 py-3 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-violet-900/40 transition-transform hover:scale-[1.03]"
        >
          Ver linhas
        </Link>
      </div>
    );
  }

  return (
    <div className="relative min-h-screen" data-testid="checkout-page">
      <div className="film-grain" />
      <div className="cinema-bg pointer-events-none fixed inset-0 opacity-60" />

      {/* Letterbox header */}
      <header className="relative z-10 border-b border-violet-500/20 bg-black/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-4 px-4 py-4">
          <Link
            to="/"
            data-testid="checkout-back-link"
            className="flex items-center gap-2 rounded-full px-3 py-2 text-sm text-white/70 transition-colors hover:bg-white/5 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" /> Loja
          </Link>
          <div className="mx-auto text-center">
            <p className="text-[10px] font-semibold uppercase tracking-[0.4em] text-amber-300">
              {brand.name} — Cena final
            </p>
            <h1 className="font-display text-2xl tracking-wide text-white sm:text-3xl">
              CHECKOUT
            </h1>
          </div>
          <span className="w-[72px]" />
        </div>
      </header>

      <main className="relative z-10 mx-auto grid max-w-6xl grid-cols-1 gap-6 px-4 py-8 lg:grid-cols-[1fr_380px]">
        <div className="flex flex-col gap-6">
          <Scene num={1} title="Seus dados" icon={User}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <input
                data-testid="checkout-name-input"
                className={`${inputCls} sm:col-span-2`}
                placeholder="Nome completo *"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              <input
                data-testid="checkout-phone-input"
                className={inputCls}
                placeholder="WhatsApp / Telefone *"
                inputMode="numeric"
                value={phone}
                onChange={(e) => setPhone(maskPhone(e.target.value))}
              />
              <input
                data-testid="checkout-email-input"
                className={inputCls}
                placeholder="E-mail (opcional)"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>
          </Scene>

          <Scene num={2} title="Entrega" icon={MapPin}>
            <div className="relative flex max-w-xs items-center">
              <input
                data-testid="checkout-cep-input"
                className={inputCls}
                placeholder="CEP *"
                inputMode="numeric"
                value={cep}
                onChange={(e) => setCep(maskCep(e.target.value))}
              />
              {cepLoading && (
                <Loader2 className="absolute right-3 h-4 w-4 animate-spin text-violet-300" />
              )}
            </div>
            <p className="mt-1.5 text-[11px] text-white/40">
              Digite o CEP e o frete é calculado automaticamente.
            </p>
            {cepError && (
              <p data-testid="checkout-cep-error" className="mt-2 text-xs text-red-400">
                {cepError}
              </p>
            )}

            {shippingData && (
              <motion.div
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-4"
              >
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-6">
                  <input
                    data-testid="checkout-street-input"
                    className={`${inputCls} sm:col-span-4`}
                    placeholder="Rua / Avenida"
                    value={street}
                    onChange={(e) => setStreet(e.target.value)}
                  />
                  <input
                    data-testid="checkout-number-input"
                    className={`${inputCls} sm:col-span-2`}
                    placeholder="Número *"
                    value={number}
                    onChange={(e) => setNumber(e.target.value)}
                  />
                  <input
                    data-testid="checkout-complement-input"
                    className={`${inputCls} sm:col-span-2`}
                    placeholder="Complemento"
                    value={complement}
                    onChange={(e) => setComplement(e.target.value)}
                  />
                  <input
                    data-testid="checkout-neighborhood-input"
                    className={`${inputCls} sm:col-span-2`}
                    placeholder="Bairro"
                    value={neighborhood}
                    onChange={(e) => setNeighborhood(e.target.value)}
                  />
                  <input
                    data-testid="checkout-city-input"
                    className={`${inputCls} sm:col-span-1`}
                    placeholder="Cidade"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                  />
                  <input
                    data-testid="checkout-state-input"
                    className={`${inputCls} sm:col-span-1`}
                    placeholder="UF"
                    maxLength={2}
                    value={uf}
                    onChange={(e) => setUf(e.target.value.toUpperCase())}
                  />
                </div>

                <p className="mt-5 mb-2 font-head text-xs font-600 uppercase tracking-wider text-white/60">
                  Escolha o frete — {shippingData.region}
                </p>
                <div data-testid="checkout-shipping-options" className="flex flex-col gap-2">
                  {shippingData.options.map((o) => {
                    const sel = shippingSel?.id === o.id;
                    return (
                      <button
                        key={o.id}
                        type="button"
                        data-testid={`checkout-shipping-${o.id}`}
                        onClick={() => setShippingSel(o)}
                        className={`flex items-center justify-between rounded-2xl border px-4 py-3.5 text-left transition-all ${
                          sel
                            ? "border-violet-500/70 bg-violet-600/20 shadow-lg shadow-violet-900/30"
                            : "border-white/10 bg-white/5 hover:border-violet-500/40"
                        }`}
                      >
                        <span className="flex items-center gap-3">
                          <span
                            className={`flex h-5 w-5 items-center justify-center rounded-full border-2 ${
                              sel ? "border-violet-400" : "border-white/25"
                            }`}
                          >
                            {sel && <span className="h-2.5 w-2.5 rounded-full bg-violet-400" />}
                          </span>
                          <span>
                            <span className="block text-sm font-medium text-white">{o.label}</span>
                            <span className="block text-xs text-white/50">{o.eta}</span>
                          </span>
                        </span>
                        <span
                          className={`font-head text-base font-600 ${
                            o.price === 0 ? "text-emerald-400" : "text-amber-300"
                          }`}
                        >
                          {o.price === 0 ? "GRÁTIS" : formatBRL(o.price)}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </motion.div>
            )}
          </Scene>

          <Scene num={3} title="Pagamento" icon={CreditCard}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {PAYMENTS.map((p) => {
                const sel = payment === p.id;
                const Icon = p.icon;
                return (
                  <button
                    key={p.id}
                    type="button"
                    data-testid={`checkout-payment-${p.id}`}
                    onClick={() => setPayment(p.id)}
                    className={`flex flex-col items-start gap-2 rounded-2xl border p-4 text-left transition-all ${
                      sel
                        ? "border-amber-400/70 bg-amber-400/10 shadow-lg shadow-amber-900/20"
                        : "border-white/10 bg-white/5 hover:border-amber-400/40"
                    }`}
                  >
                    <Icon className={`h-5 w-5 ${sel ? "text-amber-300" : "text-white/60"}`} />
                    <span className="font-head text-sm font-600 uppercase tracking-wide text-white">
                      {p.label}
                    </span>
                    <span className="text-[11px] leading-snug text-white/50">{p.desc}</span>
                  </button>
                );
              })}
            </div>
            <p className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-3 text-xs text-emerald-300/90">
              <MessageCircle className="h-4 w-4 shrink-0" />
              Ao finalizar, seu pedido é enviado para nosso WhatsApp {brand.whatsappDisplay} com
              todos os detalhes para concluir o pagamento.
            </p>
          </Scene>
        </div>

        {/* Summary */}
        <motion.aside
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="h-fit lg:sticky lg:top-6"
        >
          <div data-testid="checkout-summary" className="glass rounded-3xl p-6">
            <h2 className="font-head text-lg font-600 uppercase tracking-wide text-white">
              Resumo do pedido
            </h2>
            <ul className="mt-4 flex max-h-64 flex-col gap-3 overflow-y-auto pr-1">
              {items.map((i) => (
                <li key={i.id} className="flex items-center gap-3">
                  <img
                    src={i.image}
                    alt={i.name}
                    className="h-12 w-12 shrink-0 rounded-lg object-cover"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-1 text-xs font-medium text-white">{i.name}</p>
                    <p className="text-[11px] text-white/50">
                      {i.qty}x {formatBRL(i.price)}
                    </p>
                  </div>
                  <span className="font-head text-sm text-amber-300">
                    {formatBRL(i.price * i.qty)}
                  </span>
                </li>
              ))}
            </ul>

            <div className="mt-5 flex flex-col gap-2 border-t border-white/10 pt-4 text-sm">
              <div className="flex justify-between text-white/60">
                <span>Subtotal</span>
                <span data-testid="checkout-subtotal">{formatBRL(subtotal)}</span>
              </div>
              <div className="flex justify-between text-white/60">
                <span>Frete</span>
                <span data-testid="checkout-shipping-price">
                  {shippingSel
                    ? shippingSel.price === 0
                      ? "GRÁTIS"
                      : formatBRL(shippingSel.price)
                    : "—"}
                </span>
              </div>
              <div className="mt-1 flex items-end justify-between">
                <span className="font-head text-sm uppercase tracking-wide text-white/80">
                  Total
                </span>
                <span data-testid="checkout-total" className="font-display text-3xl text-gradient">
                  {formatBRL(total)}
                </span>
              </div>
            </div>

            <button
              data-testid="checkout-submit-button"
              onClick={submit}
              disabled={submitting}
              className="mt-5 flex w-full items-center justify-center gap-2 rounded-full bg-gradient-to-r from-emerald-500 to-green-600 px-6 py-4 font-head text-sm font-600 uppercase tracking-wider text-white shadow-lg shadow-emerald-900/30 transition-transform hover:scale-[1.02] active:scale-95 disabled:opacity-60"
            >
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              {submitting ? "Registrando pedido..." : "Finalizar pedido"}
            </button>
            <p className="mt-3 text-center text-[11px] text-white/40">
              Compra 100% segura • Pedido registrado + envio pelo WhatsApp
            </p>
          </div>
        </motion.aside>
      </main>
    </div>
  );
}
