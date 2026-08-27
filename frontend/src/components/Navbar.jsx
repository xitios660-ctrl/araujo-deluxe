import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { List, X, UserGear } from "@phosphor-icons/react";

const LINKS = [
  { label: "Serviços", id: "#servicos" },
  { label: "Agendar", id: "#agendar" },
  { label: "Minha reserva", id: "#consultar" },
  { label: "O Estúdio", id: "#sobre" },
  { label: "Contato", id: "#contato" },
];

export const Navbar = ({ scrollTo }) => {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const go = (id) => {
    setOpen(false);
    scrollTo(id);
  };

  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      className={`fixed top-0 inset-x-0 z-50 ${scrolled || open ? "glass shadow-sm" : "bg-transparent"}`}
      data-testid="navbar"
    >
      <div className="max-w-7xl mx-auto px-6 lg:px-10 h-[70px] flex items-center justify-between">
        <button onClick={() => go("#hero")} className={`font-display text-2xl tracking-tight ${scrolled || open ? "text-foreground" : "text-white"}`} data-testid="navbar-logo">
          Araújo <span className="italic text-primary">Deluxe</span>
        </button>
        <nav className="hidden md:flex items-center gap-8">
          {LINKS.map((l) => (
            <button
              key={l.id}
              onClick={() => go(l.id)}
              className={`text-sm font-medium tracking-wide transition-colors duration-300 hover:text-primary ${scrolled ? "text-foreground/80" : "text-white/90"}`}
              data-testid={`navbar-link-${l.label.toLowerCase().replace(/\s/g, "-")}`}
            >
              {l.label}
            </button>
          ))}
          <Link
            to="/admin"
            className={`text-sm font-medium tracking-wide flex items-center gap-1.5 transition-colors duration-300 hover:text-primary ${scrolled ? "text-foreground/80" : "text-white/90"}`}
            data-testid="navbar-admin-link"
          >
            <UserGear size={16} /> Área do Gestor
          </Link>
          <button
            onClick={() => go("#agendar")}
            className="rounded-full bg-primary text-white text-sm font-semibold px-6 py-2.5 transition-transform duration-300 hover:scale-105 hover:bg-[#a3822b]"
            data-testid="navbar-cta-button"
          >
            Agendar horário
          </button>
        </nav>
        <button className={`md:hidden ${scrolled || open ? "text-foreground" : "text-white"}`} onClick={() => setOpen(!open)} data-testid="navbar-mobile-toggle">
          {open ? <X size={26} /> : <List size={26} />}
        </button>
      </div>
      {open && (
        <div className="md:hidden glass border-t border-border px-6 py-6 flex flex-col gap-4" data-testid="navbar-mobile-menu">
          {LINKS.map((l) => (
            <button key={l.id} onClick={() => go(l.id)} className="text-left text-base font-medium text-foreground/90">
              {l.label}
            </button>
          ))}
          <Link to="/admin" className="text-left text-base font-medium text-foreground/90 flex items-center gap-2" data-testid="navbar-mobile-admin-link">
            <UserGear size={18} /> Área do Gestor
          </Link>
          <button onClick={() => go("#agendar")} className="rounded-full bg-primary text-white font-semibold px-6 py-3 mt-2">
            Agendar horário
          </button>
        </div>
      )}
    </motion.header>
  );
};
