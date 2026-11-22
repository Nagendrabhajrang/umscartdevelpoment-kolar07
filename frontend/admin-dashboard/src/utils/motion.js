/**
 * Shared Framer Motion variants.
 *
 * Every animation here is cheap (transform/opacity only) and the app honours
 * the OS "reduce motion" setting: `useReducedMotion()` from framer-motion is
 * read by PageTransition, and variants collapse to a no-op when it is set.
 */

export const pageVariants = {
  initial: { opacity: 0, y: 12 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.28, ease: [0.16, 1, 0.3, 1] } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.18, ease: "easeIn" } },
};

export const fadeUp = {
  hidden: { opacity: 0, y: 16 },
  show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: [0.16, 1, 0.3, 1] } },
};

export const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.045, delayChildren: 0.02 } },
};

export const cardHover = {
  rest: { scale: 1 },
  hover: { scale: 1.02, transition: { duration: 0.18, ease: "easeOut" } },
  tap: { scale: 0.985 },
};

export const cartBump = {
  initial: { scale: 1 },
  pop: { scale: [1, 1.35, 0.92, 1], transition: { duration: 0.42, ease: "easeOut" } },
};

export const toastVariants = {
  initial: { opacity: 0, y: -14, scale: 0.97 },
  animate: { opacity: 1, y: 0, scale: 1, transition: { duration: 0.22, ease: "easeOut" } },
  exit: { opacity: 0, y: -10, scale: 0.97, transition: { duration: 0.16 } },
};

export const modalVariants = {
  initial: { opacity: 0, scale: 0.96, y: 8 },
  animate: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.22, ease: [0.16, 1, 0.3, 1] } },
  exit: { opacity: 0, scale: 0.97, y: 6, transition: { duration: 0.15 } },
};
