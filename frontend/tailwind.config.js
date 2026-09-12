/** @type {import('tailwindcss').Config} */

// همهٔ رنگ‌ها از CSS variable می‌آیند تا دارک مود با یک کلاس عوض شود
// و هیچ هگز خامی داخل کامپوننت‌ها لازم نباشد.
const token = (name) => ({ opacityValue }) =>
  opacityValue === undefined
    ? `rgb(var(--${name}))`
    : `rgb(var(--${name}) / ${opacityValue})`;

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Vazirmatn", "Tahoma", "system-ui", "sans-serif"] },
      colors: {
        bg: token("bg"),
        surface: {
          DEFAULT: token("surface"),
          raised: token("surface-raised"),
        },
        border: {
          DEFAULT: token("border"),
          strong: token("border-strong"),
        },
        text: {
          DEFAULT: token("text"),
          soft: token("text-soft"),
          mute: token("text-mute"),
        },
        brand: {
          DEFAULT: token("brand"),
          fg: token("brand-fg"),
          soft: token("brand-soft"),
          text: token("brand-text"),
        },
        gain: { DEFAULT: token("gain"), soft: token("gain-soft") },
        loss: { DEFAULT: token("loss"), soft: token("loss-soft") },
        warn: { DEFAULT: token("warn"), soft: token("warn-soft") },
      },
      borderColor: { DEFAULT: token("border") },
      ringColor: { DEFAULT: token("brand") },
    },
  },
  plugins: [],
};
