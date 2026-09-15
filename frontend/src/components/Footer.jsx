import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { InstagramLogo, WhatsappLogo, MapPin, Clock } from "@phosphor-icons/react";
import { api } from "../lib/api";

export const Footer = ({ scrollTo }) => {
  const [wa, setWa] = useState("");
  useEffect(() => {
    api.get("/studio-info").then((r) => setWa(r.data.whatsapp)).catch(() => {});
  }, []);
  return (
  <footer id="contato" className="bg-[#221A0E] text-white grain relative" data-testid="footer-section">
    <div className="max-w-7xl mx-auto px-6 lg:px-10 py-20 relative z-10">
      <div className="grid md:grid-cols-3 gap-12">
        <div>
          <p className="font-display text-3xl">
            Araújo <span className="italic text-primary">Deluxe</span>
          </p>
          <p className="text-white/50 text-sm leading-relaxed mt-4 max-w-xs">
            Lash design, sobrancelhas e nail design de alto padrão. Agende online e viva a experiência.
          </p>
          <div className="flex gap-3 mt-6">
            <a href="https://instagram.com" target="_blank" rel="noreferrer" className="rounded-full glass-dark p-3 transition-colors duration-300 hover:bg-primary" data-testid="footer-instagram-link">
              <InstagramLogo size={20} />
            </a>
            <a href={`https://wa.me/${wa}`} target="_blank" rel="noreferrer" className="rounded-full glass-dark p-3 transition-colors duration-300 hover:bg-primary" data-testid="footer-whatsapp-link">
              <WhatsappLogo size={20} />
            </a>
          </div>
        </div>
        <div>
          <p className="uppercase tracking-[0.25em] text-xs text-primary font-semibold mb-5 flex items-center gap-2">
            <Clock size={14} /> Horários de atendimento
          </p>
          <ul className="text-sm text-white/70 space-y-2.5">
            <li className="flex justify-between max-w-xs"><span>Segunda a sexta</span><span className="text-white">9h · 11h · 15h30 · 17h</span></li>
            <li className="flex justify-between max-w-xs"><span>Sábado</span><span className="text-white">9h · 11h · 14h · 16h · 18h</span></li>
            <li className="flex justify-between max-w-xs"><span>Domingo</span><span className="text-white/40">Fechado</span></li>
          </ul>
          <button onClick={() => scrollTo("#agendar")} className="mt-6 rounded-full bg-primary text-white text-sm font-semibold px-7 py-3 transition-transform duration-300 hover:scale-105" data-testid="footer-book-button">
            Agendar agora
          </button>
        </div>
        <div>
          <p className="uppercase tracking-[0.25em] text-xs text-primary font-semibold mb-5 flex items-center gap-2">
            <MapPin size={14} /> Atendimento
          </p>
          <p className="text-sm text-white/70 leading-relaxed">
            Atendimento com hora marcada.
            <br /> O sinal de reserva é pago via PIX e o comprovante pode ser enviado pelo próprio site. Ele entra em análise e o resultado chega pelo WhatsApp.
          </p>
        </div>
      </div>
      <div className="border-t border-white/10 mt-16 pt-8 flex flex-col sm:flex-row items-center justify-between gap-4">
        <p className="text-white/35 text-xs">© {new Date().getFullYear()} Araújo Deluxe. Todos os direitos reservados.</p>
        <Link to="/admin" className="text-white/35 text-xs hover:text-primary transition-colors duration-300" data-testid="footer-admin-link">
          Área do Gestor
        </Link>
      </div>
    </div>
    </footer>
  );
};
