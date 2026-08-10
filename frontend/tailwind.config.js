/** @type {import('tailwindcss').Config} */
// Tokens del design system "ActiveExam Design System" (Stitch). Mantener en sync.
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Tokens como OBJETO anidado. `bg-primary` cae a `primary.DEFAULT`;
        // `bg-primary-500` cae a `primary.500`; `bg-primary-container` cae a
        // `primary.container`. Una sola fuente de verdad, escala completa, sin
        // tener que agregar key por key cada vez que se necesita un nuevo paso.

        // ── PRIMARY — azul (#164DE6) ─────────────────────────────────────────
        primary: {
          DEFAULT: "#164DE6",   // azul institucional
          50:  "#eef1fd",
          100: "#d5dcfb",
          200: "#abb9f7",
          300: "#7490f1",
          400: "#4469eb",
          500: "#164DE6",
          600: "#1240c4",
          700: "#0e33a2",
          800: "#0b2780",
          900: "#081c5e",
          // Alias semánticos del design system
          container: "#4469eb",   // bg fuerte (un paso más claro que el default)
          fixed: "#d5dcfb",       // fondo suave (chips, íconos)
          "fixed-dim": "#abb9f7", // borde sobre fixed
        },
        "on-primary": "#ffffff",
        "on-primary-container": "#eef1fd",
        "on-primary-fixed": "#081c5e",
        "on-primary-fixed-variant": "#0e33a2",
        "inverse-primary": "#abb9f7",

        // ── SECONDARY — misma familia para coherencia ───────────────────────
        secondary: {
          DEFAULT: "#1d4ed8",
          container: "#3b82f6",
          fixed: "#dbeafe",
          "fixed-dim": "#93c5fd",
        },
        "on-secondary": "#ffffff",
        "on-secondary-container": "#eff6ff",
        "on-secondary-fixed": "#0c2766",
        "on-secondary-fixed-variant": "#1d4ed8",

        // ── TERTIARY — gris violáceo (uso puntual) ──────────────────────────
        tertiary: {
          DEFAULT: "#515067",
          container: "#696880",
          fixed: "#e2e0fc",
          "fixed-dim": "#c6c4df",
        },
        "on-tertiary": "#ffffff",
        "on-tertiary-container": "#ece9ff",
        "on-tertiary-fixed": "#1a1a2e",
        "on-tertiary-fixed-variant": "#45455b",

        // ── ERROR / DANGER ──────────────────────────────────────────────────
        error: {
          DEFAULT: "#ba1a1a",
          50:  "#fef2f2",
          100: "#fee2e2",
          200: "#fecaca",
          500: "#ef4444",
          600: "#dc2626",
          700: "#b91c1c",
          800: "#991b1b",
          900: "#7f1d1d",
          container: "#ffdad6",
        },
        "on-error": "#ffffff",
        "on-error-container": "#93000a",

        // ── SUCCESS ─────────────────────────────────────────────────────────
        success: {
          DEFAULT: "#059669",
          50:  "#ecfdf5",
          100: "#d1fae5",
          200: "#a7f3d0",
          500: "#10b981",
          600: "#059669",
          700: "#047857",
          800: "#065f46",
          900: "#064e3b",
          container: "#d1fae5",
        },

        // ── WARNING ─────────────────────────────────────────────────────────
        warning: {
          // DEFAULT = 500 (ámbar vivo), no 700 — este es el tono de referencia
          // usado en la verificación biométrica del alumno (primer ingreso).
          DEFAULT: "#f59e0b",
          50:  "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
          800: "#92400e",
          900: "#78350f",
          container: "#fef3c7",
        },

        // ── INFO — teal sutil (verde-azulado), diferencia clara del primary
        // azul sin caer en cyan estridente.
        info: {
          DEFAULT: "#0d9488",   // teal-600
          50:  "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          500: "#14b8a6",       // teal-500 (gradient start)
          600: "#0d9488",       // teal-600 (gradient end)
          700: "#0f766e",
          container: "#ccfbf1",
        },
        "on-info": "#ffffff",

        // ── SURFACE — neutros puros (alineado a la referencia active-ia).
        //   Antes slate (azulado); ahora gris neutro Tailwind, sin tinte.
        //   Fondo app #fafafa, cards #ffffff, borde #e5e5e5 → contraste sutil.
        surface: {
          DEFAULT: "#fafafa",   // neutral-50: fondo principal de la app
          50:  "#fafafa",
          100: "#f5f5f5",
          200: "#e5e5e5",
          300: "#d4d4d4",
          400: "#a3a3a3",
          500: "#737373",
          600: "#525252",
          700: "#404040",
          800: "#262626",
          900: "#171717",
          // Alias semánticos del design system
          dim: "#d4d4d4",
          bright: "#ffffff",
          variant: "#e5e5e5",
          tint: "#164DE6",
          "container-lowest": "#ffffff",
          "container-low": "#f5f5f5",
          container: "#ededed",
          "container-high": "#e5e5e5",
          "container-highest": "#d4d4d4",
        },
        // Textos neutros (foreground/muted de la referencia).
        "on-surface": "#262626",
        "on-surface-variant": "#737373",
        "inverse-surface": "#262626",
        "inverse-on-surface": "#fafafa",

        // ── Tokens globales ─────────────────────────────────────────────────
        background: "#fafafa",
        "on-background": "#262626",
        outline: "#737373",
        "outline-variant": "#e5e5e5",
      },
      borderRadius: {
        // Escala mas mesurada (institucional). Cada token bajo un nivel respecto
        // al anterior — antes rounded-xl daba 24px, ahora 12px.
        DEFAULT: "0.375rem", // 6px
        sm: "0.25rem",       // 4px
        md: "0.5rem",        // 8px
        lg: "0.625rem",      // 10px
        xl: "0.75rem",       // 12px
        "2xl": "1rem",       // 16px — solo para contenedores grandes
        full: "9999px",
      },
      spacing: {
        base: "4px",
        xs: "8px",
        sm: "12px",
        md: "16px",
        lg: "24px",
        xl: "32px",
        xxl: "48px",
        gutter: "24px",
        "container-max": "1280px",
        "sidebar-width": "240px",
        "sidebar-collapsed": "60px",
        "topbar-height": "56px",
      },
      fontFamily: {
        // Tipografía unificada: Inter en todo (más limpia/moderna para dashboard).
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        headline: ['Inter', 'system-ui', 'sans-serif'],
      },
      fontSize: {
        "display-lg": ["48px", { lineHeight: "56px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "headline-lg": ["32px", { lineHeight: "40px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "headline-md": ["24px", { lineHeight: "32px", fontWeight: "600" }],
        "title-lg": ["20px", { lineHeight: "28px", fontWeight: "600" }],
        "title-md": ["16px", { lineHeight: "24px", fontWeight: "600" }],
        "title-sm": ["14px", { lineHeight: "20px", fontWeight: "600" }],
        "body-lg": ["16px", { lineHeight: "24px", fontWeight: "400" }],
        "body-md": ["15px", { lineHeight: "22px", fontWeight: "400" }],
        "label-lg": ["16px", { lineHeight: "24px", letterSpacing: "0.01em", fontWeight: "600" }],
        "label-md": ["14px", { lineHeight: "20px", letterSpacing: "0.01em", fontWeight: "600" }],
        "label-sm": ["12px", { lineHeight: "16px", fontWeight: "500" }],
      },
      maxWidth: {
        "container-max": "1280px",
      },
      boxShadow: {
        xs: "0 1px 2px 0 rgba(0,0,0,0.05)",
        sm: "0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px -1px rgba(0,0,0,0.1)",
        md: "0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)",
        lg: "0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)",
        card: "0 1px 2px 0 rgba(16,24,40,0.04), 0 1px 3px 0 rgba(16,24,40,0.06)",
        "card-lg": "0 2px 4px -1px rgba(16,24,40,0.04), 0 8px 16px -6px rgba(16,24,40,0.08)",
      },
    },
  },
  plugins: [],
}
