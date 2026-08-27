import { motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { Sparkle, Star, CalendarCheck } from "@phosphor-icons/react";

const PHOTO =
  "https://customer-assets-v7afamib.emergentagent.net/job_2ecbabc4-43e0-4dfb-b605-c98ca3e80ae8/artifacts/qeep7eq1_510bdf44-0bef-4d2e-8617-e694926efc03.jpeg";

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.14, delayChildren: 0.35 } },
};
const item = {
  hidden: { y: 60, opacity: 0 },
  show: { y: 0, opacity: 1, transition: { duration: 1, ease: [0.22, 1, 0.36, 1] } },
};

export const Hero = ({ scrollTo }) => {
  const mx = useMotionValue(0);
  const my = useMotionValue(0);
  const rotateX = useSpring(useTransform(my, [-0.5, 0.5], [7, -7]), { stiffness: 55, damping: 14 });
  const rotateY = useSpring(useTransform(mx, [-0.5, 0.5], [-10, 10]), { stiffness: 55, damping: 14 });
  const layerX = useSpring(useTransform(mx, [-0.5, 0.5], [-24, 24]), { stiffness: 45, damping: 16 });
  const layerY = useSpring(useTransform(my, [-0.5, 0.5], [-16, 16]), { stiffness: 45, damping: 16 });

  const onMove = (e) => {
    mx.set(e.clientX / window.innerWidth - 0.5);
    my.set(e.clientY / window.innerHeight - 0.5);
  };

  return (
    <section id="hero" onMouseMove={onMove} className="relative min-h-screen flex items-center overflow-hidden grain perspective-wrap" data-testid="hero-section">
      <img
        src={PHOTO}
        alt="Araújo Deluxe"
        className="absolute inset-0 w-full h-full object-cover"
        style={{ objectPosition: "68% 22%" }}
        data-testid="hero-photo"
      />
      <div className="absolute inset-0 bg-gradient-to-r from-[#221A0E]/90 via-[#221A0E]/55 to-[#221A0E]/20" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#221A0E]/75 via-transparent to-transparent" />

      <div className="relative z-10 max-w-7xl mx-auto px-6 lg:px-10 w-full pt-28 pb-20 grid lg:grid-cols-12 gap-12 items-center">
        <motion.div variants={container} initial="hidden" animate="show" className="lg:col-span-7">
          <motion.p variants={item} className="text-primary uppercase tracking-[0.35em] text-xs sm:text-sm font-semibold mb-6 flex items-center gap-3">
            <Sparkle size={16} weight="fill" /> Lash Designer · Estúdio de Beleza
          </motion.p>
          <motion.h1 variants={item} className="font-display text-white text-5xl sm:text-6xl lg:text-7xl leading-[1.05] tracking-tight">
            Olhares que
            <br />
            <em className="text-shimmer">hipnotizam</em>,
            <br />
            detalhes que <em className="italic text-primary">encantam</em>
          </motion.h1>
          <motion.p variants={item} className="text-white/75 text-base md:text-lg leading-relaxed max-w-xl mt-8">
            Extensão de cílios, design de sobrancelhas e nail design de alto padrão.
            Agende seu horário em segundos — nosso sistema conhece a agenda do estúdio e mostra apenas os horários realmente livres.
          </motion.p>
          <motion.div variants={item} className="flex flex-wrap items-center gap-4 mt-10">
            <button
              onClick={() => scrollTo("#agendar")}
              className="group rounded-full bg-primary text-white font-semibold px-9 py-4 text-sm sm:text-base transition-transform duration-300 hover:scale-105 hover:bg-[#a3822b] flex items-center gap-3"
              data-testid="hero-book-button"
            >
              <CalendarCheck size={20} weight="bold" className="transition-transform duration-300 group-hover:rotate-12" />
              Agendar meu horário
            </button>
            <button
              onClick={() => scrollTo("#servicos")}
              className="rounded-full glass-dark text-white font-medium px-8 py-4 text-sm sm:text-base transition-colors duration-300 hover:bg-white/20"
              data-testid="hero-services-button"
            >
              Ver serviços
            </button>
          </motion.div>
          <motion.div variants={item} className="flex items-center gap-10 mt-14">
            {[
              ["+500", "olhares transformados"],
              ["5.0", "avaliação das clientes"],
              ["15", "serviços exclusivos"],
            ].map(([num, label]) => (
              <div key={label}>
                <p className="font-display text-3xl sm:text-4xl text-white">{num}</p>
                <p className="text-white/60 text-xs sm:text-sm mt-1 max-w-[120px]">{label}</p>
              </div>
            ))}
          </motion.div>
        </motion.div>

        <div className="hidden lg:block lg:col-span-5 relative h-[480px]">
          <motion.div style={{ rotateX, rotateY }} className="absolute inset-0 preserve-3d">
            <motion.div
              initial={{ opacity: 0, scale: 0.85 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.9, duration: 1.2, ease: [0.22, 1, 0.36, 1] }}
              className="glass-dark rounded-3xl p-8 absolute top-10 right-4 w-[320px] float-slow"
              style={{ transform: "translateZ(60px)" }}
              data-testid="hero-3d-card"
            >
              <div className="flex items-center gap-1 text-primary mb-4">
                {[...Array(5)].map((_, i) => (
                  <Star key={i} size={16} weight="fill" />
                ))}
              </div>
              <p className="font-display italic text-white text-xl leading-snug">"O melhor investimento no meu olhar. Acordo pronta todos os dias."</p>
              <p className="text-white/60 text-sm mt-4">— Cliente Fox Eyes</p>
            </motion.div>
            <motion.div
              style={{ x: layerX, y: layerY, transform: "translateZ(120px)" }}
              initial={{ opacity: 0, y: 40 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 1.3, duration: 1 }}
              className="glass rounded-2xl px-6 py-5 absolute bottom-16 left-0 shadow-xl"
            >
              <p className="text-xs uppercase tracking-widest text-muted-foreground">Próximo horário livre</p>
              <p className="font-display text-2xl text-foreground mt-1">Consulte em tempo real ↓</p>
            </motion.div>
          </motion.div>
        </div>
      </div>

      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10">
        <motion.div animate={{ y: [0, 10, 0] }} transition={{ repeat: Infinity, duration: 2.2 }} className="w-[26px] h-[42px] rounded-full border-2 border-white/40 flex justify-center pt-2">
          <div className="w-1 h-2.5 rounded-full bg-white/70" />
        </motion.div>
      </div>
    </section>
  );
};

