/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./app/**/*.py",
  ],
  safelist: [
    // 동적으로 생성되는 클래스 보호
    'sidebar-navy',
    'text-header',
    'rounded-button',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Noto Sans KR', 'Malgun Gothic', '맑은 고딕', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        'navy': {
          50: '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d6fe',
          300: '#a4b8fc',
          400: '#8191f8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
      },
    },
  },
  plugins: [],
  // 프로덕션 최적화
  ...(process.env.NODE_ENV === 'production' && {
    purge: {
      enabled: true,
      content: [
        "./templates/**/*.html",
        "./app/**/*.py",
      ],
    },
  }),
}
