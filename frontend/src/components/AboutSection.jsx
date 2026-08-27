import { motion } from "framer-motion";
import { HeartStraight, Medal, ShieldCheck } from "@phosphor-icons/react";

const IMG =
  "https://images.unsplash.com/photo-1759262151080-e05ba1c6294f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjA1NTZ8MHwxfHNlYXJjaHw0fHxsdXh1cnklMjBiZWF1dHklMjBzYWxvbiUyMGludGVyaW9yJTIwbnVkZSUyMGFlc3RoZXRpY3xlbnwwfHx8fDE3ODQ4NTU4NjN8MA&ixlib=rb-4.1.0&q=85";

const FEATURES = [
  { icon: Medal, title: "Técnicas premium", text: "Fox Eyes, Glamour, Egípcio, Híbrido e Brasileiro — sempre com materiais de alta qualidade." },
  { icon: ShieldCheck, title: "Biossegurança", text: "Higienização rigorosa, produtos hipoalergênicos e cuidado com a saúde dos seus fios." },
  { icon: HeartStraight, title: "Experiência acolhedora", text: "Um momento só seu, em um ambiente pensado para o seu conforto e bem-estar." },
];

const fade = (delay = 0) => ({
  initial: { opacity: 0, y: 40 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-80px" },
  transition: { duration: 0.9, delay, ease: [0.22, 1, 0.36, 1] },
});

export const AboutSection = () => (
  <section id="sobre" className="max-w-7xl mx-auto px-6 lg:px-10 py-24 lg:py-32" data-testid="about-section">
    <div className="grid lg:grid-cols-12 gap-12 lg:gap-16 items-center">
      <motion.div {...fade(0)} className="lg:col-span-5 relative">
        <div className="rounded-[2.5rem] overflow-hidden max-h-[80vh]">
          <img src={IMG} alt="Estúdio Araújo Deluxe" className="w-full h-full object-cover aspect-[4/5]" />
        </div>
        <div className="glass rounded-2xl px-7 py-5 absolute -bottom-6 -right-2 sm:right-[-24px] shadow-xl">
          <p className="font-display text-3xl text-primary">5.0 ★</p>
          <p className="text-xs text-muted-foreground mt-0.5">avaliação das clientes</p>
        </div>
      </motion.div>
      <div className="lg:col-span-7">
        <motion.p {...fade(0)} className="text-primary uppercase tracking-[0.3em] text-xs font-semibold mb-4">
          O Estúdio
        </motion.p>
        <motion.h2 {...fade(0.1)} className="font-display text-4xl sm:text-5xl lg:text-6xl tracking-tight text-foreground leading-[1.08]">
          Beleza é um <em className="italic text-primary">ritual</em>, não uma pressa
        </motion.h2>
        <motion.p {...fade(0.2)} className="text-muted-foreground leading-relaxed mt-6 max-w-2xl text-sm md:text-base">
          No Araújo Deluxe, cada atendimento é exclusivo. Trabalhamos com horários dedicados — por isso a agenda é limitada e
          cada cliente recebe atenção total, do design dos cílios ao acabamento das unhas.
        </motion.p>
        <div className="grid sm:grid-cols-3 gap-6 mt-12">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} {...fade(0.25 + i * 0.1)} className="bg-white border border-border rounded-3xl p-7 transition-[transform,box-shadow] duration-300 hover:-translate-y-1 hover:shadow-lg">
              <f.icon size={28} className="text-primary" weight="duotone" />
              <h3 className="font-display text-lg text-foreground mt-4">{f.title}</h3>
              <p className="text-muted-foreground text-xs leading-relaxed mt-2">{f.text}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </div>
  </section>
);
