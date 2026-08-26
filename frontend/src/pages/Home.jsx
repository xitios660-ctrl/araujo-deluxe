import React, { useState } from "react";
import AnnouncementBar from "../components/AnnouncementBar";
import Header from "../components/Header";
import Hero from "../components/Hero";
import BenefitsBar from "../components/BenefitsBar";
import ProductSection from "../components/ProductSection";
import CtaBanner from "../components/CtaBanner";
import Testimonials from "../components/Testimonials";
import Newsletter from "../components/Newsletter";
import Footer from "../components/Footer";
import ProductTrailer from "../components/ProductTrailer";
import CartDrawer from "../components/CartDrawer";
import KiteLine from "../components/KiteLine";
import { destaques, lancamentos, promocoes } from "../mock";

export default function Home() {
  const [active, setActive] = useState(null);

  return (
    <div className="relative min-h-screen">
      <div className="film-grain" />
      <KiteLine />
      <AnnouncementBar />
      <Header />
      <main>
        <Hero />
        <BenefitsBar />
        <ProductSection
          id="destaques"
          scene="01"
          eyebrow="Os mais desejados"
          title="DESTAQUES"
          subtitle="As linhas que dominam o céu da quebrada. Selecionadas por performance no cortante."
          products={destaques}
          onOpen={setActive}
        />
        <CtaBanner />
        <ProductSection
          id="lancamentos"
          scene="02"
          eyebrow="Recém chegadas"
          title="LANÇAMENTOS"
          subtitle="Novidades quentes direto da Indonésia para o seu carretel."
          products={lancamentos}
          onOpen={setActive}
          accent="gold"
        />
        <ProductSection
          id="promocoes"
          scene="03"
          countdown
          eyebrow="Ofertas relâmpago"
          title="PROMOÇÕES"
          subtitle="Preço de quem entende. Aproveite enquanto o vento sopra a seu favor."
          products={promocoes}
          onOpen={setActive}
        />
        <Testimonials />
        <Newsletter />
      </main>
      <Footer />
      <ProductTrailer product={active} onClose={() => setActive(null)} />
      <CartDrawer />
    </div>
  );
}
