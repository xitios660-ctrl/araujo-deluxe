const ITEMS = ["Volume Brasileiro", "Fox Eyes", "Brow Lamination", "Nail Design", "Volume Glamour", "Henna", "Volume Egípcio", "Blindagem"];

export const Marquee = () => (
  <div className="bg-[#221A0E] py-5 overflow-hidden select-none" data-testid="marquee-strip">
    <div className="marquee-track flex whitespace-nowrap w-max">
      {[...ITEMS, ...ITEMS].map((t, i) => (
        <span key={i} className="font-display italic text-white/70 text-lg md:text-xl mx-6 flex items-center gap-6">
          {t} <span className="text-primary not-italic">✦</span>
        </span>
      ))}
    </div>
  </div>
);
