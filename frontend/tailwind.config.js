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

        // ── PRIMARY — azul institucional profundo (#004BA8) ─────────────────
        primary: {
          DEFAULT: "#004BA8",   // azul institucional
          50:  "#e8eff8",
          100: "#cdddf1",
          200: "#9bbbe3",
          300: "#6899d5",
          400: "#3677c7",
          500: "#0a5fc0",
          600: "#004BA8",
          700: "#003d8a",
          800: "#002f6c",
          900: "#00214e",
          // Alias semánticos del design system
          container: "#0a5fc0",   // bg fuerte (un paso más claro que el default)
          fixed: "#d6e4f5",       // fondo suave (chips, íconos)
          "fixed-dim": "#9bbbe3", // borde sobre fixed
        },
        "on-primary": "#ffffff",
        "on-primary-container": "#d6e4f5",
        "on-primary-fixed": "#00214e",
        "on-primary-fixed-variant": "#003d8a",
        "inverse-primary": "#9bbbe3",

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
          DEFAULT: "#b45309",
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

        // ── SURFACE — slate como base de fondos/bordes ──────────────────────
        surface: {
          DEFAULT: "#f8fafc",   // slate-50: fondo principal de la app
          50:  "#f8fafc",
          100: "#f1f5f9",
          200: "#e2e8f0",
          300: "#cbd5e1",
          400: "#94a3b8",
          500: "#64748b",
          600: "#475569",
          700: "#334155",
          800: "#1e293b",
          900: "#0f172a",
          // Alias semánticos del design system
          dim: "#cbd5e1",
          bright: "#ffffff",
          variant: "#e2e8f0",
          tint: "#2563eb",
          "container-lowest": "#ffffff",
          "container-low": "#eef2f7",
          container: "#e4eaf2",
          "container-high": "#d6dfe9",
          "container-highest": "#c8d3e0",
        },
        "on-surface": "#0f172a",
        "on-surface-variant": "#475569",
        "inverse-surface": "#1e293b",
        "inverse-on-surface": "#f1f5f9",

        // ── Tokens globales ─────────────────────────────────────────────────
        background: "#f8fafc",
        "on-background": "#0f172a",
        outline: "#64748b",
        "outline-variant": "#e2e8f0",
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
