import React, { useEffect, useState } from "react";
import { Search, User, ShoppingCart, Menu, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { brand, nav } from "../mock";
import { useCart } from "../context/CartContext";

export default function Header() {
  const { count, setOpen } = useCart();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-50 transition-all duration-300 ${
        scrolled
          ? "border-b border-violet-500/20 bg-[#0b0817]/85 backdrop-blur-xl"
          : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
        {/* Logo */}
        <a href="#inicio" className="group flex shrink-0 items-center gap-3">
          <span className="relative flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-purple-800 shadow-lg shadow-violet-900/50">
            <span className="font-display text-lg leading-none text-white">DC</span>
            <span className="absolute -bottom-1 -right-1 h-3 w-3 rounded-full bg-amber-400 ring-2 ring-[#0b0817]" />
          </span>
          <span className="hidden flex-col leading-none sm:flex">
            <span className="font-display text-lg tracking-wide text-white">
              {brand.name}
            </span>
            <span className="text-[10px] font-semibold tracking-[0.32em] text-violet-300">
              {brand.subtitle}
            </span>
          </span>
        </a>

        {/* Search */}
        <div className="relative hidden flex-1 items-center md:flex">
          <Search className="absolute left-4 h-4 w-4 text-muted-foreground" />
          <input
            placeholder="O que você está caçando hoje?"
            className="h-11 w-full rounded-full border border-violet-500/20 bg-white/5 pl-11 pr-4 text-sm text-white placeholder:text-muted-foreground focus:border-violet-500/60 focus:outline-none focus:ring-2 focus:ring-violet-600/30"
          />
        </div>

        {/* Actions */}
        <div className="ml-auto flex items-center gap-1 md:ml-0">
          <button className="hidden items-center gap-2 rounded-full px-3 py-2 text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white lg:flex">
            <User className="h-5 w-5" />
            <span className="hidden xl:inline">Minha conta</span>
          </button>
          <button
            data-testid="header-cart-button"
            onClick={() => setOpen(true)}
            className="relative flex items-center gap-2 rounded-full px-3 py-2 text-sm text-white/80 transition-colors hover:bg-white/5 hover:text-white"
          >
            <span className="relative">
              <ShoppingCart className="h-5 w-5" />
              {count > 0 && (
                <span className="absolute -right-2 -top-2 flex h-4 min-w-4 items-center justify-center rounded-full bg-amber-400 px-1 text-[10px] font-bold text-black">
                  {count}
                </span>
              )}
            </span>
            <span className="hidden xl:inline">Carrinho</span>
          </button>
          <button
            className="flex h-10 w-10 items-center justify-center rounded-full text-white md:hidden"
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="Menu"
          >
            {menuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
          </button>
        </div>
      </div>

      {/* Desktop nav */}
      <nav className="hidden border-t border-white/5 md:block">
        <ul className="mx-auto flex max-w-7xl items-center justify-center gap-8 px-4 py-2.5">
          {nav.map((n) => (
            <li key={n.href}>
              <a
                href={n.href}
                className="group relative font-head text-sm font-500 uppercase tracking-wider text-white/75 transition-colors hover:text-white"
              >
                {n.label}
                <span className="absolute -bottom-1 left-0 h-0.5 w-0 bg-amber-400 transition-all duration-300 group-hover:w-full" />
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.nav
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden border-t border-white/10 bg-[#0b0817]/95 backdrop-blur-xl md:hidden"
          >
            <div className="px-4 py-4">
              <div className="relative mb-4 flex items-center">
                <Search className="absolute left-4 h-4 w-4 text-muted-foreground" />
                <input
                  placeholder="Buscar linhas..."
                  className="h-11 w-full rounded-full border border-violet-500/20 bg-white/5 pl-11 pr-4 text-sm text-white placeholder:text-muted-foreground focus:outline-none"
                />
              </div>
              <ul className="flex flex-col">
                {nav.map((n) => (
                  <li key={n.href}>
                    <a
                      href={n.href}
                      onClick={() => setMenuOpen(false)}
                      className="block border-b border-white/5 py-3 font-head text-base uppercase tracking-wide text-white/80"
                    >
                      {n.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </motion.nav>
        )}
      </AnimatePresence>
    </header>
  );
}
