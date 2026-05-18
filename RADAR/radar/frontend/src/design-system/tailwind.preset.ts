/**
 * Tailwind preset — consumes tokens.ts and exposes them as Tailwind theme values.
 *
 * Imported by tailwind.config.ts at the project root.
 * Do not duplicate token values here — always reference imports.
 */

import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";
import {
  animation,
  breakpoint,
  color,
  duration,
  ease,
  fontFamily,
  fontSize,
  fontWeight,
  keyframes,
  letterSpacing,
  lineHeight,
  radius,
  shadow,
  spacing,
  zIndex,
} from "./tokens";

const preset: Partial<Config> = {
  theme: {
    // Override defaults entirely (we want our scale to be the only one)
    screens: breakpoint,
    spacing,
    fontFamily: {
      mono: [...fontFamily.mono],
      sans: [...fontFamily.sans],
    },
    fontSize,
    fontWeight,
    lineHeight,
    letterSpacing,
    borderRadius: radius,
    boxShadow: shadow,
    transitionDuration: duration,
    transitionTimingFunction: ease,
    zIndex: Object.fromEntries(
      Object.entries(zIndex).map(([k, v]) => [k, v.toString()])
    ),
    keyframes,
    animation,

    // Extend colors (keep default layout utilities like flex, grid)
    extend: {
      colors: {
        surface: color.surface,
        line: color.line,
        fg: color.fg,
        accent: color.accent,
        status: color.status,
        tint: color.tint,
        data: color.data,
      },
    },
  },
  plugins: [
    plugin(({ addBase }) => {
      addBase({
        ":root": {
          "--surface-base": color.surface.base,
          "--surface-panel": color.surface.panel,
          "--surface-inset": color.surface.inset,
          "--surface-raised": color.surface.raised,
          "--line-subtle": color.line.subtle,
          "--line-default": color.line.default,
          "--line-strong": color.line.strong,
          "--accent-500": color.accent[500],
          "--accent-glow": color.accent.glow,
          "--fg-primary": color.fg.primary,
          "--fg-secondary": color.fg.secondary,
          "--fg-muted": color.fg.muted,
        },
        html: {
          backgroundColor: color.surface.base,
          color: color.fg.primary,
          fontFamily: fontFamily.sans.join(", "),
          fontVariantNumeric: "tabular-nums",
          fontFeatureSettings: '"cv02", "cv03", "cv04", "cv11"',
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale",
        },
        body: {
          margin: "0",
          backgroundColor: color.surface.base,
          color: color.fg.primary,
          minHeight: "100vh",
        },
        "*": {
          boxSizing: "border-box",
        },
        "@media (prefers-reduced-motion: reduce)": {
          "*, *::before, *::after": {
            animationDuration: "0.001ms !important",
            animationIterationCount: "1 !important",
            transitionDuration: "0.001ms !important",
            scrollBehavior: "auto !important",
          },
        },
      });
    }),
  ],
};

export default preset;
