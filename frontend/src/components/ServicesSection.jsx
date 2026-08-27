import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Eye, Scissors, HandPalm, Clock, ArrowRight } from "@phosphor-icons/react";
import { api, BRL, CATEGORY_LABELS } from "../lib/api";

const ICONS = { cilios: Eye, sobrancelhas: Scissors, unhas: HandPalm };

export const ServicesSection = ({ onBook }) => {
  const [services, setServices] = useState([]);
  const [cat, setCat] = useState("cilios");

  useEffect(() => {
    api.get("/services").then((r) => setServices(r.data)).catch(() => {});
  }, []);

  const filtered = services.filter((s) => s.category === cat);

  return (
    <section id="servicos" className="max-w-7xl mx-auto px-6 lg:px-10 py-24 lg:py-32" data-testid="services-section">
      <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-8 mb-14">
        <div>
          <p className="text-primary uppercase tracking-[0.3em] text-xs font-semibold mb-4">Menu de serviços</p>
          <h2 className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-tight text-foreground">
            Rituais de beleza <em className="italic text-primary">sob medida</em>
          </h2>
        </div>
        <div className="flex gap-2 flex-wrap">
          {Object.keys(CATEGORY_LABELS).map((c) => {
            const Icon = ICONS[c];
            return (
              <button
                key={c}
                onClick={() => setCat(c)}
                className={`rounded-full px-6 py-3 text-sm font-semibold flex items-center gap-2 transition-colors duration-300 ${
                  cat === c ? "bg-foreground text-white" : "bg-white border border-border text-foreground hover:border-primary"
                }`}
                data-testid={`services-tab-${c}`}
              >
                <Icon size={17} weight={cat === c ? "fill" : "regular"} />
                {CATEGORY_LABELS[c]}
              </button>
            );
          })}
        </div>
      </div>

      <AnimatePresence mode="wait">
        <motion.div
          key={cat}
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -20 }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
        >
          {filtered.map((s, i) => (
            <motion.div
              key={s.id}
              initial={{ opacity: 0, y: 24 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.07, duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className={`group bg-white border border-border rounded-3xl p-8 flex flex-col justify-between transition-[transform,box-shadow] duration-300 hover:-translate-y-1.5 hover:shadow-xl ${
                i === 0 ? "md:col-span-2 lg:col-span-1 lg:row-span-2 lg:flex" : ""
              }`}
              data-testid={`service-card-${s.id}`}
            >
              <div>
                <div className="flex items-start justify-between gap-4">
                  <h3 className="font-display text-2xl text-foreground leading-tight">{s.name}</h3>
                  <p className="font-display text-2xl text-primary whitespace-nowrap">{BRL(s.price)}</p>
                </div>
                <p className="text-muted-foreground text-sm leading-relaxed mt-4">{s.description}</p>
                <div className="flex items-center gap-4 mt-6 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Clock size={14} /> {s.duration}
                  </span>
                  {s.deposit > 0 && (
                    <span className="rounded-full bg-accent text-foreground/70 px-3 py-1 font-medium">Sinal {BRL(s.deposit)}</span>
                  )}
                </div>
              </div>
              <button
                onClick={() => onBook(s)}
                className="mt-8 self-start rounded-full border border-foreground text-foreground text-sm font-semibold px-6 py-2.5 flex items-center gap-2 transition-colors duration-300 group-hover:bg-foreground group-hover:text-white"
                data-testid={`service-book-${s.id}`}
              >
                Agendar <ArrowRight size={15} className="transition-transform duration-300 group-hover:translate-x-1" />
              </button>
            </motion.div>
          ))}
        </motion.div>
      </AnimatePresence>
    </section>
  );
};
