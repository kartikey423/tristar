/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/frontend/app/**/*.{js,ts,jsx,tsx,mdx}',
    './src/frontend/components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        ct: {
          red: '#D52B1E',
          'red-dark': '#B10806',
          'red-light': '#FEF2F2',
        },
        sidebar: {
          DEFAULT: '#1A1A1A',
          hover: '#2A2A2A',
          active: '#252525',
        },
        surface: {
          DEFAULT: '#FCFAF9',
          low: '#F6F3F2',
          card: '#FFFFFF',
          dim: '#EAE7E7',
        },
      },
      fontFamily: {
        sans: [
          'Public Sans',
          'Inter',
          'system-ui',
          '-apple-system',
          'sans-serif',
        ],
      },
      fontSize: {
        'display': ['2.25rem', { lineHeight: '2.5rem', letterSpacing: '-0.02em', fontWeight: '600' }],
        'headline': ['1.5rem', { lineHeight: '2rem', fontWeight: '600' }],
        'title': ['1rem', { lineHeight: '1.5rem', fontWeight: '500' }],
        'body': ['0.875rem', { lineHeight: '1.375rem' }],
        'label': ['0.6875rem', { lineHeight: '1rem', letterSpacing: '0.05em', fontWeight: '500' }],
      },
      borderRadius: {
        DEFAULT: '4px',
        sm: '2px',
        md: '6px',
        lg: '8px',
      },
      boxShadow: {
        'ambient': '0 12px 32px -4px rgba(28, 27, 27, 0.08)',
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.04)',
      },
    },
  },
  plugins: [],
};
