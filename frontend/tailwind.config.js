/** @type {import('tailwindcss').Config} */
// Token màu lấy từ các màn hình Stitch đã sinh (project 10235864807415215328).
// Sidebar dùng navy #0F172A, primary xanh #2563EB, success #16A34A, warning amber.
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#2563EB',
          hover: '#1D4ED8',
          50: '#EFF6FF',
          100: '#DBEAFE',
          600: '#2563EB',
          700: '#1D4ED8',
          800: '#1E40AF',
        },
        navy: {
          DEFAULT: '#0F172A',
          deep: '#0B1120',
          700: '#1E293B',
          800: '#1F2937',
        },
        success: {
          DEFAULT: '#16A34A',
          50: '#F0FDF4',
          700: '#15803D',
        },
        warning: {
          DEFAULT: '#CA8A04',
          50: '#FFFBEB',
          200: '#FDE68A',
          700: '#B45309',
          900: '#78350F',
        },
        error: {
          DEFAULT: '#DC2626',
          50: '#FEF2F2',
          700: '#B91C1C',
        },
        slate: {
          50: '#F8FAFC',
          100: '#F1F5F9',
          200: '#E2E8F0',
          300: '#CBD5E1',
          400: '#94A3B8',
          500: '#64748B',
          600: '#475569',
          700: '#334155',
          800: '#1E293B',
          900: '#0F172A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"Fira Code"', 'monospace'],
      },
      fontSize: {
        'headline-lg': ['24px', { lineHeight: '1.25', letterSpacing: '-0.01em' }],
        'headline-sm': ['18px', { lineHeight: '1.3' }],
        'body-md': ['14px', { lineHeight: '1.6' }],
        'body-md-medium': ['14px', { lineHeight: '1.5', fontWeight: '500' }],
        'label-md': ['13px', { lineHeight: '1.2', fontWeight: '600' }],
        'label-sm': ['12px', { lineHeight: '1.3', fontWeight: '500' }],
      },
      borderRadius: {
        sm: '4px',
        DEFAULT: '8px',
        md: '8px',
        lg: '12px',
        full: '9999px',
      },
      boxShadow: {
        subtle: '0 1px 2px 0 rgba(0,0,0,0.04)',
        medium: '0 4px 12px 0 rgba(0,0,0,0.06)',
        large: '0 12px 32px 0 rgba(0,0,0,0.10)',
      },
      maxWidth: {
        content: '1024px',
      },
    },
  },
  plugins: [],
}
