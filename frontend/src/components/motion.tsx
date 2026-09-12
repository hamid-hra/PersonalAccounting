import { motion, type Variants } from "framer-motion";
import { useEffect, useRef, useState } from "react";

import { useReducedMotion } from "../lib/theme";

/*
  حرکت باید معنا برساند، نه اینکه فقط تکان بخورد.

  • ورودِ صفحه: کمی از پایین می‌آید — یعنی «محتوای تازه».
  • ردیف‌های جدول: پلکانی، تا چشم ترتیب را بگیرد.
  • همه روی transform و opacity‌اند (نه width/height) تا لایه‌بندی مرورگر
    نشکند و روی موبایل هم روان بماند.
  • هرکس reduced-motion خواسته، همه‌چیز فوری و بدون حرکت می‌شود.
*/

const EASE = [0.22, 1, 0.36, 1] as const;

export const pageVariants: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.28, ease: EASE } },
};

export const listVariants: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.03, delayChildren: 0.02 } },
};

export const itemVariants: Variants = {
  hidden: { opacity: 0, y: 6 },
  show: { opacity: 1, y: 0, transition: { duration: 0.22, ease: EASE } },
};

export function Page({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div variants={pageVariants} initial="hidden" animate="show" className={className}>
      {children}
    </motion.div>
  );
}

export function Stagger({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div variants={listVariants} initial="hidden" animate="show" className={className}>
      {children}
    </motion.div>
  );
}

export function Item({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div variants={itemVariants} className={className}>
      {children}
    </motion.div>
  );
}

/**
 * عدد که به مقدار تازه می‌رود، به‌جای اینکه بپرد.
 *
 * حرکت اینجا کار می‌کند: چشم می‌فهمد عدد «تغییر کرد» و چقدر.
 */
export function CountUp({
  value,
  format,
  className,
}: {
  value: number;
  format: (n: number) => string;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(value);
  const fromRef = useRef(value);
  const rafRef = useRef<number>();

  useEffect(() => {
    if (reduced || fromRef.current === value) {
      setShown(value);
      fromRef.current = value;
      return;
    }
    const from = fromRef.current;
    const delta = value - from;
    const duration = 550;
    const start = performance.now();

    const tick = (now: number) => {
      const p = Math.min((now - start) / duration, 1);
      // easeOutCubic — سریع شروع می‌شود و نرم می‌ایستد
      const eased = 1 - Math.pow(1 - p, 3);
      setShown(from + delta * eased);
      if (p < 1) rafRef.current = requestAnimationFrame(tick);
      else fromRef.current = value;
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [value, reduced]);

  return <span className={className}>{format(Math.round(shown))}</span>;
}

export { motion };
