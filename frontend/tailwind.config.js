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
        // Índigo institucional VIVO (formal, con presencia — no apagado).
        "primary": "#4f46e5",
        "primary-container": "#6366f1",
        "primary-700": "#4338ca",
        "primary-800": "#3730a3",
        "on-primary": "#ffffff",
        "on-primary-container": "#edeaff",
        "primary-fixed": "#e2dfff",
        "primary-fixed-dim": "#c1c1ff",
        "on-primary-fixed": "#0a006b",
        "on-primary-fixed-variant": "#3533b0",
        "inverse-primary": "#c1c1ff",
        "secondary": "#5845ca",
        "secondary-container": "#7260e5",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#fffbff",
        "secondary-fixed": "#e5deff",
        "secondary-fixed-dim": "#c7bfff",
        "on-secondary-fixed": "#180065",
        "on-secondary-fixed-variant": "#432bb4",
        "tertiary": "#515067",
        "tertiary-container": "#696880",
        "on-tertiary": "#ffffff",
        "on-tertiary-container": "#ece9ff",
        "tertiary-fixed": "#e2e0fc",
        "tertiary-fixed-dim": "#c6c4df",
        "on-tertiary-fixed": "#1a1a2e",
        "on-tertiary-fixed-variant": "#45455b",
        "error": "#ba1a1a",
        "on-error": "#ffffff",
        "error-container": "#ffdad6",
        "on-error-container": "#93000a",
        // Paleta de superficies basada en slate — fondos limpios, sin tinte cremita.
        "surface": "#f8fafc",            // slate-50: fondo principal de la app
        "surface-dim": "#cbd5e1",        // slate-300
        "surface-bright": "#ffffff",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f1f5f9",   // slate-100: fondo de cards sutiles
        "surface-container": "#e2e8f0",       // slate-200: separadores fuertes / chips
        "surface-container-high": "#cbd5e1",  // slate-300
        "surface-container-highest": "#94a3b8", // slate-400
        "surface-variant": "#e2e8f0",
        "surface-tint": "#4f46e5",
        "on-surface": "#0f172a",         // slate-900
        "on-surface-variant": "#475569", // slate-600
        "inverse-surface": "#1e293b",    // slate-800
        "inverse-on-surface": "#f1f5f9",
        "background": "#f8fafc",
        "on-background": "#0f172a",
        "outline": "#64748b",            // slate-500
        "outline-variant": "#e2e8f0",    // slate-200 — bordes sutiles tipo dashboard moderno
        // Escala numérica adicional (para alinear con utilidades estándar).
        "surface-50":  "#f8fafc",
        "surface-100": "#f1f5f9",
        "surface-200": "#e2e8f0",
        "surface-300": "#cbd5e1",
        "surface-400": "#94a3b8",
        "surface-500": "#64748b",
        "surface-600": "#475569",
        "surface-700": "#334155",
        "surface-800": "#1e293b",
        "surface-900": "#0f172a",
        // tokens de estado semántico (para badges de severidad)
        "success": "#15803d",
        "success-container": "#dcfce7",
        "warning": "#b45309",
        "warning-container": "#fef3c7",
        // Escala viva para gradientes de stat cards (fondo de color + texto blanco).
        "success-500": "#22c55e",
        "success-600": "#16a34a",
        "warning-500": "#f59e0b",
        "warning-600": "#d97706",
        "error-500": "#ef4444",
        "error-600": "#dc2626",
        "info": "#2563eb",
        "info-500": "#3b82f6",
        "info-600": "#2563eb",
        "info-container": "#dbeafe",
        "on-info": "#ffffff",
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        sm: "0.25rem",
        md: "0.75rem",
        lg: "1rem",
        xl: "1.5rem",
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
        // Sombras sutiles estilo "flat minimalism": apenas perceptibles, sin nubes
        // difusas. La definición la da el borde, no la sombra.
        card: "0 1px 2px 0 rgba(16,24,40,0.04), 0 1px 3px 0 rgba(16,24,40,0.06)",
        "card-lg": "0 2px 4px -1px rgba(16,24,40,0.04), 0 8px 16px -6px rgba(16,24,40,0.08)",
      },
    },
  },
  plugins: [],
}
