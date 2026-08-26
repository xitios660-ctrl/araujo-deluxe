import React from "react";
import { Truck, CreditCard, ShieldCheck, MessageCircle } from "lucide-react";
import { benefits } from "../mock";
import { useReveal } from "../hooks/useReveal";

const ICONS = { Truck, CreditCard, ShieldCheck, MessageCircle };

export default function BenefitsBar() {
  const [ref, visible] = useReveal();
  return (
    <section ref={ref} className="relative z-10 mx-auto max-w-7xl px-4 py-10 sm:py-14">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {benefits.map((b, i) => {
          const Icon = ICONS[b.icon] || Truck;
          return (
            <div
              key={b.title}
              className={`group glass flex items-center gap-4 rounded-2xl p-4 transition-all duration-700 hover:border-violet-500/50 ${
                visible ? "translate-y-0 opacity-100" : "translate-y-8 opacity-0"
              }`}
              style={{ transitionDelay: `${i * 90}ms` }}
            >
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-violet-600/20 text-violet-300 transition-colors group-hover:bg-violet-600/40 group-hover:text-violet-200">
                <Icon className="h-6 w-6" />
              </span>
              <div className="min-w-0">
                <p className="font-head text-sm font-600 uppercase tracking-wide text-white">
                  {b.title}
                </p>
                <p className="truncate text-xs text-muted-foreground">{b.desc}</p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
