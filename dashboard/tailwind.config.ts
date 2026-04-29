import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#eef5ff',
          100: '#d9e8ff',
          200: '#bcd4ff',
          300: '#8eb5fe',
          400: '#5a8dfb',
          500: '#3b6ef8',
          600: '#2650ed',
          700: '#1e3fd9',
          800: '#1f35b0',
          900: '#1e318b',
          950: '#162057',
        },
        income:  '#5DCAA5',
        expense: '#E85D24',
      },
    },
  },
  plugins: [],
};

export default config;
