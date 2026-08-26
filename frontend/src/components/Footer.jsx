import React from "react";
import { Instagram, Facebook, MessageCircle, MapPin, Wind } from "lucide-react";
import { brand, nav } from "../mock";

export default function Footer() {
  return (
    <footer className="relative z-10 border-t border-white/10 bg-[#0a0714]">
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-10 px-4 py-14 md:grid-cols-4">
        <div className="md:col-span-2">
          <div className="flex items-center gap-3">
            <span className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-800">
              <span className="font-display text-lg text-white">DC</span>
            </span>
            <div>
              <p className="font-display text-xl text-white">{brand.name}</p>
              <p className="text-[10px] font-semibold tracking-[0.32em] text-violet-300">
                {brand.subtitle}
              </p>
            </div>
          </div>
          <p className="mt-5 max-w-sm text-sm text-white/60">
            Linhas indonésia de alta performance para pipeiros exigentes.
            Blindada, áspera e emborrachada — a linha que corta o céu.
          </p>
          <div className="mt-6 flex gap-3">
            <a
              href={brand.instagramUrl}
              target="_blank"
              rel="noreferrer"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white/70 transition-colors hover:border-violet-500/50 hover:text-white"
            >
              <Instagram className="h-5 w-5" />
            </a>
            <a
              href="#"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white/70 transition-colors hover:border-violet-500/50 hover:text-white"
            >
              <Facebook className="h-5 w-5" />
            </a>
            <a
              href={`https://wa.me/${brand.whatsapp}`}
              target="_blank"
              rel="noreferrer"
              className="flex h-10 w-10 items-center justify-center rounded-full border border-white/15 text-white/70 transition-colors hover:border-emerald-500/50 hover:text-white"
            >
              <MessageCircle className="h-5 w-5" />
            </a>
          </div>
        </div>

        <div>
          <p className="font-head text-sm font-600 uppercase tracking-widest text-white">
            Navegação
          </p>
          <ul className="mt-4 flex flex-col gap-2.5">
            {nav.map((n) => (
              <li key={n.href}>
                <a
                  href={n.href}
                  className="text-sm text-white/60 transition-colors hover:text-violet-300"
                >
                  {n.label}
                </a>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="font-head text-sm font-600 uppercase tracking-widest text-white">
            Contato
          </p>
          <ul className="mt-4 flex flex-col gap-3 text-sm text-white/60">
            <li className="flex items-center gap-2">
              <MessageCircle className="h-4 w-4 text-emerald-400" />
              {brand.whatsappDisplay}
            </li>
            <li className="flex items-center gap-2">
              <Instagram className="h-4 w-4 text-fuchsia-400" />@{brand.instagram}
            </li>
            <li className="flex items-center gap-2">
              <MapPin className="h-4 w-4 text-violet-300" />
              São Paulo • Brasil
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-white/5 py-5">
        <p className="px-4 text-center text-xs text-white/40">
          © {new Date().getFullYear()} {brand.name} — {brand.subtitle}. Réplica
          cinematográfica com dados fictícios para demonstração.
        </p>
      </div>

      {/* WhatsApp float */}
      <a
        href={`https://wa.me/${brand.whatsapp}`}
        target="_blank"
        rel="noreferrer"
        className="animate-pulse-ring fixed bottom-6 right-6 z-[95] flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-emerald-500 to-green-600 text-white shadow-xl transition-transform hover:scale-110"
        aria-label="WhatsApp"
      >
        <Wind className="h-7 w-7" />
      </a>
    </footer>
  );
}
