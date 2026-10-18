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
                        sm:      '0 1px 2px 0 rgb(20 33 61 / 0.06)',
                        DEFAULT: '0 1px 3px 0 rgb(20 33 61 / 0.10), 0 1px 2px -1px rgb(20 33 61 / 0.08)',
                        md:      '0 2px 8px 0 rgb(20 33 61 / 0.14)',
                        lg:      '0 2px 8px 0 rgb(20 33 61 / 0.18)',
                        xl:      '0 8px 24px -4px rgb(20 33 61 / 0.28)',
                        '2xl':   '0 8px 24px -4px rgb(20 33 61 / 0.28)',
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
                        slate:   { 50: '#F4F3EF', 100: '#EBE9E2', 200: '#D9D6CD', 300: '#BDB9AE', 400: '#646972', 500: '#535862', 600: '#3E4553', 700: '#2A3345', 800: '#14213D', 900: '#0E172B', 950: '#080E1C' },
                        amber:   { 50: '#FBE9DD', 100: '#FDDAC5', 200: '#FFC1A1', 300: '#FCA67F', 400: '#EA7B4C', 500: '#BF4A10', 600: '#A33D0B', 700: '#8A320E', 800: '#72290E', 900: '#5A210E', 950: '#3F1508' },
                        orange:  { 50: '#F9F2E4', 100: '#F4E3C4', 200: '#EFCD97', 300: '#E5B568', 400: '#CF901C', 500: '#A46500', 600: '#8E5400', 700: '#784500', 800: '#643800', 900: '#502B00', 950: '#381C00' },
                        red:     { 50: '#F7E1DF', 100: '#FDD5D1', 200: '#FFB9B1', 300: '#FD978C', 400: '#ED695C', 500: '#C7342A', 600: '#B3261E', 700: '#971B17', 800: '#7E1414', 900: '#641212', 950: '#460A0B' },
                        green:   { 50: '#E3F1E8', 100: '#CCEAD6', 200: '#A9E0BD', 300: '#7ED09C', 400: '#4AB074', 500: '#2E8151', 600: '#276B43', 700: '#1F5A37', 800: '#194B2D', 900: '#133C22', 950: '#0C2815' },
                        emerald: { 50: '#E3F1E8', 100: '#CCEAD6', 200: '#A9E0BD', 300: '#7ED09C', 400: '#4AB074', 500: '#2E8151', 600: '#276B43', 700: '#1F5A37', 800: '#194B2D', 900: '#133C22', 950: '#0C2815' },
                        blue:    { 50: '#E2EAF6', 100: '#D0E1FB', 200: '#B2D1FF', 300: '#90BCFF', 400: '#6498EB', 500: '#3D6FC2', 600: '#2F5DA8', 700: '#254D90', 800: '#204079', 900: '#1A3363', 950: '#112245' },
                        // named tokens — for NEW code only (nothing existing is renamed in this batch)
                        surface: '#F4F3EF', 'surface-2': '#EBE9E2', line: '#D9D6CD', 'line-2': '#BDB9AE',
                        ink: '#0E172B', 'ink-2': '#535862', 'ink-3': '#646972',
                        navy: '#14213D', 'navy-2': '#1F3159',
                        action: '#BF4A10', 'action-2': '#A33D0B', 'action-soft': '#FBE9DD', brand: '#E8641B',
                        ok: '#276B43', 'ok-soft': '#E3F1E8', warn: '#A46500', 'warn-soft': '#F9F2E4',
                        danger: '#B3261E', 'danger-soft': '#F7E1DF', info: '#2F5DA8', 'info-soft': '#E2EAF6',
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