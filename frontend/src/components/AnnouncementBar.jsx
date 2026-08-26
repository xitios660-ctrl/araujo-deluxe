import React from "react";
import { Zap, Truck, ShieldCheck, Instagram, Facebook } from "lucide-react";
import { brand } from "../mock";

const items = [
  { icon: Zap, text: "FRETE COM SUPER DESCONTO PARA TODO BRASIL" },
  { icon: Truck, text: "ENVIO EXPRESSO EM ATÉ 24H" },
  { icon: ShieldCheck, text: "LOJA 100% SEGURA \u2022 PAGAMENTO PROTEGIDO" },
  { icon: Zap, text: "PARCELE EM ATÉ 12X NO CARTÃO" },
];

export default function AnnouncementBar() {
  const loop = [...items, ...items, ...items, ...items];
  return (
    <div className="relative z-40 flex items-center bg-gradient-to-r from-violet-700 via-purple-600 to-violet-700 text-white">
      <div className="hidden shrink-0 items-center gap-3 px-4 py-1.5 sm:flex">
        <a
          href={brand.instagramUrl}
          target="_blank"
          rel="noreferrer"
          className="transition-transform hover:scale-110"
          aria-label="Instagram"
        >
          <Instagram className="h-4 w-4" />
        </a>
        <a href="#" className="transition-transform hover:scale-110" aria-label="Facebook">
          <Facebook className="h-4 w-4" />
        </a>
      </div>
      <div className="relative flex-1 overflow-hidden py-1.5">
        <div className="flex w-max animate-marquee items-center gap-10 whitespace-nowrap">
          {loop.map((it, idx) => {
            const Icon = it.icon;
            return (
              <span
                key={idx}
                className="flex items-center gap-2 text-[11px] font-semibold tracking-[0.18em] text-white/90"
              >
                <Icon className="h-3.5 w-3.5 text-amber-300" />
                {it.text}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
