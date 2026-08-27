import { useEffect, useRef, useState } from "react";
import Lenis from "lenis";
import { Navbar } from "@/components/Navbar";
import { Hero } from "@/components/Hero";
import { Marquee } from "@/components/Marquee";
import { ServicesSection } from "@/components/ServicesSection";
import { BookingSection } from "@/components/BookingSection";
import { MyBookings } from "@/components/MyBookings";
import { AboutSection } from "@/components/AboutSection";
import { Footer } from "@/components/Footer";

export default function Landing() {
  const lenisRef = useRef(null);
  const [preselected, setPreselected] = useState(null);

  useEffect(() => {
    const lenis = new Lenis({ lerp: 0.09, smoothWheel: true });
    lenisRef.current = lenis;
    let rafId;
    const raf = (t) => {
      lenis.raf(t);
      rafId = requestAnimationFrame(raf);
    };
    rafId = requestAnimationFrame(raf);
    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
    };
  }, []);

  const scrollTo = (id) => {
    if (lenisRef.current) lenisRef.current.scrollTo(id, { offset: -70, duration: 1.4 });
  };

  const bookService = (service) => {
    setPreselected(service);
    scrollTo("#agendar");
  };

  return (
    <div className="bg-background text-foreground overflow-x-clip">
      <Navbar scrollTo={scrollTo} />
      <Hero scrollTo={scrollTo} />
      <Marquee />
      <ServicesSection onBook={bookService} />
      <BookingSection preselected={preselected} />
      <MyBookings />
      <AboutSection />
      <Footer scrollTo={scrollTo} />
    </div>
  );
}
