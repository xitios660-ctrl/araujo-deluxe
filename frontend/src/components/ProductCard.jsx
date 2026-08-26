import React, { useRef, useState } from "react";
import { motion } from "framer-motion";
import { Star, Plus, Play } from "lucide-react";
import { formatBRL } from "../mock";
import { useCart } from "../context/CartContext";

function Stars({ rating }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((n) => (
        <Star
          key={n}
          className={`h-3.5 w-3.5 ${
            n <= Math.round(rating)
              ? "fill-amber-400 text-amber-400"
              : "fill-transparent text-white/25"
          }`}
        />
      ))}
    </div>
  );
}

export default function ProductCard({ product, index = 0, onOpen }) {
  const { addItem } = useCart();
  const cardRef = useRef(null);
  const [tilt, setTilt] = useState({ rx: 0, ry: 0 });

  const onMove = (e) => {
    const rect = cardRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = (e.clientX - rect.left) / rect.width - 0.5;
    const py = (e.clientY - rect.top) / rect.height - 0.5;
    setTilt({ rx: py * -8, ry: px * 10 });
  };
  const reset = () => setTilt({ rx: 0, ry: 0 });

  return (
    <motion.div
      initial={{ opacity: 0, y: 40 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.5, delay: (index % 4) * 0.08 }}
      style={{ perspective: 1000 }}
    >
      <div
        ref={cardRef}
        onMouseMove={onMove}
        onMouseLeave={reset}
        style={{
          transform: `rotateX(${tilt.rx}deg) rotateY(${tilt.ry}deg)`,
          transition: "transform 0.15s ease-out",
        }}
        className="card-sheen group relative flex h-full cursor-pointer flex-col overflow-hidden rounded-2xl border border-white/10 bg-card transition-colors hover:border-violet-500/50"
        onClick={() => onOpen(product)}
      >
        {/* Image */}
        <div className="relative aspect-square overflow-hidden bg-gradient-to-br from-[#17122a] to-[#0d0a18]">
          {product.off > 0 && (
            <span className="absolute left-3 top-3 z-10 rounded-full bg-gradient-to-r from-amber-400 to-amber-500 px-2.5 py-1 text-[11px] font-bold text-black shadow-lg">
              {product.off}% OFF
            </span>
          )}
          {product.badge && (
            <span className="absolute right-3 top-3 z-10 rounded-full border border-violet-400/40 bg-violet-600/30 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-violet-100 backdrop-blur">
              {product.badge}
            </span>
          )}
          <img
            src={product.art || product.image}
            alt={product.name}
            loading="lazy"
            onError={(e) => {
              e.currentTarget.src = product.image;
            }}
            className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-110"
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
          {/* Quick view hint */}
          <div className="absolute inset-x-0 bottom-0 flex translate-y-full items-center justify-center gap-2 bg-violet-600/80 py-2 text-xs font-semibold uppercase tracking-wider text-white backdrop-blur transition-transform duration-300 group-hover:translate-y-0">
            <Play className="h-4 w-4 fill-white" /> Assistir apresentação
          </div>
        </div>

        {/* Body */}
        <div className="flex flex-1 flex-col p-4">
          <div className="mb-2 flex flex-wrap gap-1.5">
            <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] font-medium text-violet-200">
              {product.specs.jardas}
            </span>
            <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] font-medium text-violet-200">
              {product.specs.passadas}
            </span>
          </div>
          <h3 className="font-head text-sm font-500 uppercase leading-tight text-white line-clamp-2">
            {product.name}
          </h3>
          <div className="mt-2 flex items-center gap-2">
            <Stars rating={product.rating} />
            <span className="text-[11px] text-white/40">({product.reviews})</span>
          </div>

          <div className="mt-auto pt-4">
            <div className="flex items-end justify-between gap-2">
              <div>
                {product.off > 0 && (
                  <p className="text-xs text-white/40 line-through">
                    {formatBRL(product.oldPrice)}
                  </p>
                )}
                <p className="font-display text-2xl text-white">
                  {formatBRL(product.price)}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  addItem(product);
                }}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 to-purple-500 text-white shadow-lg shadow-violet-900/40 transition-transform hover:scale-110 active:scale-95"
                aria-label="Adicionar ao carrinho"
              >
                <Plus className="h-5 w-5" />
              </button>
            </div>
            {product.freeShipping && (
              <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-emerald-400">
                Frete grátis acima de R$250
              </p>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
