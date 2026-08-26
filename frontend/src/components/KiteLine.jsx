import React, { useRef } from "react";
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useMotionValueEvent,
  useScroll,
  useSpring,
} from "framer-motion";

const PATH =
  "M -20 30 C 250 90, 720 60, 850 170 C 950 260, 400 280, 220 370 C 60 450, 620 470, 810 560 C 960 640, 350 660, 180 750 C 40 830, 700 850, 1030 960";

export default function KiteLine() {
  const { scrollYProgress } = useScroll();
  const progress = useSpring(scrollYProgress, { stiffness: 60, damping: 20, mass: 0.4 });
  const pathRef = useRef(null);
  const kx = useMotionValue(-2);
  const ky = useMotionValue(3);

  useMotionValueEvent(progress, "change", (v) => {
    const p = pathRef.current;
    if (!p) return;
    const pt = p.getPointAtLength(Math.max(0, Math.min(1, v)) * p.getTotalLength());
    kx.set((pt.x / 1000) * 100);
    ky.set((pt.y / 1000) * 100);
  });

  const left = useMotionTemplate`${kx}%`;
  const top = useMotionTemplate`${ky}%`;

  return (
    <div className="pointer-events-none fixed inset-0 z-[5]" aria-hidden="true" data-testid="kite-line">
      <svg
        className="h-full w-full"
        viewBox="0 0 1000 1000"
        preserveAspectRatio="none"
        fill="none"
      >
        <defs>
          <linearGradient id="kite-line-grad" x1="0" y1="0" x2="1000" y2="1000" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#8b5cf6" />
            <stop offset="0.55" stopColor="#a78bfa" />
            <stop offset="1" stopColor="#f59e0b" />
          </linearGradient>
        </defs>
        {/* faint guide */}
        <path d={PATH} stroke="#8b5cf6" strokeOpacity="0.08" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
        {/* glow */}
        <motion.path
          d={PATH}
          stroke="#8b5cf6"
          strokeOpacity="0.25"
          strokeWidth="6"
          vectorEffect="non-scaling-stroke"
          style={{ pathLength: progress, filter: "blur(4px)" }}
        />
        {/* cutting line */}
        <motion.path
          ref={pathRef}
          d={PATH}
          stroke="url(#kite-line-grad)"
          strokeOpacity="0.75"
          strokeWidth="2"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
          style={{ pathLength: progress }}
        />
      </svg>

      {/* kite at the tip */}
      <motion.div style={{ left, top }} className="absolute -translate-x-1/2 -translate-y-1/2">
        <motion.div
          animate={{ rotate: [40, 50, 40], y: [0, -3, 0] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
          className="relative"
        >
          <div
            className="h-4 w-4 bg-gradient-to-br from-violet-400 to-amber-400 shadow-[0_0_18px_rgba(167,139,250,0.9)]"
            style={{ clipPath: "polygon(50% 0%, 100% 50%, 50% 100%, 0% 50%)" }}
          />
          <span className="absolute -bottom-1.5 left-1/2 h-1 w-1 rounded-full bg-amber-300/80" />
          <span className="absolute -bottom-3 left-[40%] h-1 w-1 rounded-full bg-violet-300/60" />
        </motion.div>
      </motion.div>
    </div>
  );
}
