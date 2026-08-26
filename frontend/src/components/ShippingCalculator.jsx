import React, { useEffect, useState } from "react";
import axios from "axios";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, Loader2, MapPin, Truck } from "lucide-react";
import { formatBRL } from "../mock";

const API = (process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "");

export const maskCep = (v) => {
  const d = v.replace(/\D/g, "").slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
};

export default function ShippingCalculator({
  subtotal = 0,
  onSelect,
  selected,
  collapsible = false,
  className = "",
}) {
  const [expanded, setExpanded] = useState(!collapsible);
  const [cep, setCep] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const digits = cep.replace(/\D/g, "");

  useEffect(() => {
    if (digits.length !== 8) {
      setData(null);
      setError("");
      return;
    }
    let active = true;
    setLoading(true);
    setError("");
    axios
      .get(`${API}/api/shipping/${digits}`, { params: { subtotal } })
      .then((r) => {
        if (active) setData(r.data);
      })
      .catch((e) => {
        if (active) {
          setData(null);
          setError(e?.response?.data?.detail || "CEP não encontrado.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [digits, subtotal]);

  return (
    <div
      data-testid="shipping-calculator"
      className={`rounded-2xl border border-white/10 bg-white/5 ${className}`}
    >
      <button
        type="button"
        data-testid="shipping-calc-toggle"
        onClick={() => collapsible && setExpanded((v) => !v)}
        className={`flex w-full items-center gap-2 px-4 py-3 text-left ${
          collapsible ? "cursor-pointer" : "cursor-default"
        }`}
      >
        <Truck className="h-4 w-4 shrink-0 text-emerald-400" />
        <span className="font-head text-xs font-600 uppercase tracking-wider text-white/80">
          Calcular frete e prazo
        </span>
        {collapsible && (
          <ChevronDown
            className={`ml-auto h-4 w-4 text-white/50 transition-transform ${
              expanded ? "rotate-180" : ""
            }`}
          />
        )}
      </button>

      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-4 pb-4">
              <div className="relative flex items-center">
                <input
                  data-testid="shipping-cep-input"
                  value={cep}
                  onChange={(e) => setCep(maskCep(e.target.value))}
                  placeholder="Digite seu CEP"
                  inputMode="numeric"
                  className="h-11 w-full rounded-xl border border-white/10 bg-black/30 px-4 pr-10 text-sm text-white placeholder:text-white/30 focus:border-violet-500/60 focus:outline-none focus:ring-2 focus:ring-violet-600/30"
                />
                {loading && (
                  <Loader2 className="absolute right-3 h-4 w-4 animate-spin text-violet-300" />
                )}
              </div>

              {error && (
                <p data-testid="shipping-error" className="mt-2 text-xs text-red-400">
                  {error}
                </p>
              )}

              {data && (
                <div data-testid="shipping-calc-result" className="mt-3">
                  <p className="flex items-center gap-1.5 text-xs text-white/60">
                    <MapPin className="h-3.5 w-3.5 text-amber-300" />
                    {[data.address.street, data.address.neighborhood]
                      .filter(Boolean)
                      .join(", ") || data.region}{" "}
                    — {data.address.city}/{data.address.state}
                  </p>
                  <ul data-testid="shipping-options" className="mt-2 flex flex-col gap-1.5">
                    {data.options.map((o) => {
                      const isSel = selected === o.id;
                      const Row = onSelect ? "button" : "div";
                      return (
                        <Row
                          key={o.id}
                          type={onSelect ? "button" : undefined}
                          data-testid={`shipping-option-${o.id}`}
                          onClick={onSelect ? () => onSelect(o, data) : undefined}
                          className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-left transition-colors ${
                            isSel
                              ? "border-violet-500/70 bg-violet-600/20"
                              : "border-white/10 bg-black/20"
                          } ${onSelect ? "hover:border-violet-500/50" : ""}`}
                        >
                          <span className="min-w-0">
                            <span className="block text-xs font-medium text-white">
                              {o.label}
                            </span>
                            <span className="block text-[11px] text-white/50">{o.eta}</span>
                          </span>
                          <span
                            className={`font-head text-sm font-600 ${
                              o.price === 0 ? "text-emerald-400" : "text-amber-300"
                            }`}
                          >
                            {o.price === 0 ? "GRÁTIS" : formatBRL(o.price)}
                          </span>
                        </Row>
                      );
                    })}
                  </ul>
                  {subtotal < data.free_shipping_threshold && (
                    <p className="mt-2 text-[11px] text-emerald-400/80">
                      Frete grátis em compras acima de {formatBRL(data.free_shipping_threshold)}
                    </p>
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
