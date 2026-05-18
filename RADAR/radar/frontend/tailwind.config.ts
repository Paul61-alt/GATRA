import type { Config } from "tailwindcss";
import preset from "./src/design-system/tailwind.preset";

/**
 * RADAR Tailwind config.
 *
 * All theme values live in src/design-system/tokens.ts and are mapped to
 * Tailwind via src/design-system/tailwind.preset.ts. Do not add inline
 * theme values here.
 */
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  presets: [preset as Config],
};

export default config;
