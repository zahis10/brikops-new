/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
        extend: {
                borderRadius: {
                        lg: 'var(--radius)',
                        md: 'calc(var(--radius) - 2px)',
                        sm: 'calc(var(--radius) - 4px)',
                        xl: '0.5rem',
                        '2xl': '0.75rem',
                },
                boxShadow: {
                        sm:      '0 1px 2px 0 rgb(15 23 42 / 0.05)',
                        DEFAULT: '0 1px 3px 0 rgb(15 23 42 / 0.08), 0 1px 2px -1px rgb(15 23 42 / 0.06)',
                        md:      '0 2px 8px 0 rgb(15 23 42 / 0.10)',
                        lg:      '0 2px 8px 0 rgb(15 23 42 / 0.12)',
                        xl:      '0 8px 24px -4px rgb(15 23 42 / 0.20)',
                        '2xl':   '0 8px 24px -4px rgb(15 23 42 / 0.20)',
                },
                colors: {
                        background: 'hsl(var(--background))',
                        foreground: 'hsl(var(--foreground))',
                        card: {
                                DEFAULT: 'hsl(var(--card))',
                                foreground: 'hsl(var(--card-foreground))'
                        },
                        popover: {
                                DEFAULT: 'hsl(var(--popover))',
                                foreground: 'hsl(var(--popover-foreground))'
                        },
                        primary: {
                                DEFAULT: 'hsl(var(--primary))',
                                foreground: 'hsl(var(--primary-foreground))'
                        },
                        secondary: {
                                DEFAULT: 'hsl(var(--secondary))',
                                foreground: 'hsl(var(--secondary-foreground))'
                        },
                        muted: {
                                DEFAULT: 'hsl(var(--muted))',
                                foreground: 'hsl(var(--muted-foreground))'
                        },
                        accent: {
                                DEFAULT: 'hsl(var(--accent))',
                                foreground: 'hsl(var(--accent-foreground))'
                        },
                        destructive: {
                                DEFAULT: 'hsl(var(--destructive))',
                                foreground: 'hsl(var(--destructive-foreground))'
                        },
                        border: 'hsl(var(--border))',
                        input: 'hsl(var(--input))',
                        ring: 'hsl(var(--ring))',
                        chart: {
                                '1': 'hsl(var(--chart-1))',
                                '2': 'hsl(var(--chart-2))',
                                '3': 'hsl(var(--chart-3))',
                                '4': 'hsl(var(--chart-4))',
                                '5': 'hsl(var(--chart-5))'
                        },
                        // #615 — BrikOps palette. The Tailwind family names keep their MEANING; only the values change.
                        slate:   { 50: '#F8FAFC', 100: '#F1F5F9', 200: '#E2E8F0', 300: '#CBD5E1', 400: '#64748B', 500: '#526071', 600: '#475569', 700: '#334155', 800: '#1E293B', 900: '#0F172A', 950: '#020617' },
                        amber:   { 50: '#FDF3EB', 100: '#FCE4D3', 200: '#FAC8AC', 300: '#F5A77E', 400: '#F2874F', 500: '#E8641B', 600: '#D4540F', 700: '#BF4A10', 800: '#A33D0B', 900: '#8A320E', 950: '#72290E' },
                        orange:  { 50: '#FFFBEB', 100: '#FEF3C7', 200: '#FDE68A', 300: '#FCD34D', 400: '#FBBF24', 500: '#D97706', 600: '#B45309', 700: '#92400E', 800: '#78350F', 900: '#451A03', 950: '#2C1203' },
                        red:     { 50: '#FEF2F2', 100: '#FEE2E2', 200: '#FECACA', 300: '#FCA5A5', 400: '#F87171', 500: '#EF4444', 600: '#DC2626', 700: '#B91C1C', 800: '#991B1B', 900: '#7F1D1D', 950: '#450A0A' },
                        green:   { 50: '#F0FDF4', 100: '#DCFCE7', 200: '#BBF7D0', 300: '#86EFAC', 400: '#4ADE80', 500: '#22C55E', 600: '#16A34A', 700: '#15803D', 800: '#166534', 900: '#14532D', 950: '#052E16' },
                        emerald: { 50: '#F0FDF4', 100: '#DCFCE7', 200: '#BBF7D0', 300: '#86EFAC', 400: '#4ADE80', 500: '#22C55E', 600: '#16A34A', 700: '#15803D', 800: '#166534', 900: '#14532D', 950: '#052E16' },
                        blue:    { 50: '#EFF6FF', 100: '#DBEAFE', 200: '#BFDBFE', 300: '#93C5FD', 400: '#60A5FA', 500: '#3B82F6', 600: '#2563EB', 700: '#1D4ED8', 800: '#1E40AF', 900: '#1E3A8A', 950: '#172554' },
                        // named tokens — for NEW code only (nothing existing is renamed in this batch)
                        surface: '#F8FAFC', 'surface-2': '#F1F5F9', line: '#E2E8F0', 'line-2': '#CBD5E1',
                        ink: '#0F172A', 'ink-2': '#526071', 'ink-3': '#64748B',
                        navy: '#1E293B', 'navy-2': '#334155',
                        action: '#E8641B', 'action-2': '#D4540F', 'action-soft': '#FDF3EB', brand: '#E8641B',
                        ok: '#15803D', 'ok-soft': '#F0FDF4', warn: '#B45309', 'warn-soft': '#FFFBEB',
                        danger: '#DC2626', 'danger-soft': '#FEF2F2', info: '#2563EB', 'info-soft': '#EFF6FF',
                },
                fontSize: {
                        'caption': ['12px', { lineHeight: '16px', letterSpacing: '0.01em' }],
                        'body-sm': ['14px', { lineHeight: '20px' }],
                        'body':    ['16px', { lineHeight: '24px' }],
                        'subhead': ['18px', { lineHeight: '26px', fontWeight: '600' }],
                        'title':   ['24px', { lineHeight: '32px', fontWeight: '700' }],
                        'display': ['32px', { lineHeight: '40px', fontWeight: '700', letterSpacing: '-0.01em' }]
                },
                keyframes: {
                        'accordion-down': {
                                from: {
                                        height: '0'
                                },
                                to: {
                                        height: 'var(--radix-accordion-content-height)'
                                }
                        },
                        'accordion-up': {
                                from: {
                                        height: 'var(--radix-accordion-content-height)'
                                },
                                to: {
                                        height: '0'
                                }
                        }
                },
                animation: {
                        'accordion-down': 'accordion-down 0.2s ease-out',
                        'accordion-up': 'accordion-up 0.2s ease-out'
                }
        }
  },
  plugins: [require("tailwindcss-animate")],
};