'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useTheme } from './ThemeProvider';

const navLinks = [
  { href: '/',           label: 'Resumen' },
  { href: '/expenses',   label: 'Gastos' },
  { href: '/income',     label: 'Ingresos' },
  { href: '/categories', label: 'Categorías' },
];

function SunIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v2.25m6.364.386-1.591 1.591M21 12h-2.25m-.386 6.364-1.591-1.591M12 18.75V21m-4.773-4.227-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0Z" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
      <path strokeLinecap="round" strokeLinejoin="round" d="M21.752 15.002A9.72 9.72 0 0 1 18 15.75c-5.385 0-9.75-4.365-9.75-9.75 0-1.33.266-2.597.748-3.752A9.753 9.753 0 0 0 3 11.25C3 16.635 7.365 21 12.75 21a9.753 9.753 0 0 0 9.002-5.998Z" />
    </svg>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { theme, toggle } = useTheme();

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--bg-base)' }}>
      <header
        className="sticky top-0 z-40 border-b"
        style={{ backgroundColor: 'var(--bg-card)', borderColor: 'var(--border)' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            <div className="flex items-center gap-3">
              <span className="text-xl font-bold" style={{ color: 'var(--text-primary)' }}>
                💰 Fortunia
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                style={{ backgroundColor: 'var(--bg-card-2)', color: 'var(--text-muted)' }}>
                beta
              </span>
            </div>
            <button
              onClick={toggle}
              className="p-2 rounded-lg transition-colors"
              style={{ color: 'var(--text-muted)' }}
              aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
            >
              {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>

          <nav className="flex gap-1 -mb-px">
            {navLinks.map(({ href, label }) => {
              const active = pathname === href;
              return (
                <Link
                  key={href}
                  href={href}
                  className="px-4 py-3 text-sm font-medium border-b-2 transition-colors"
                  style={{
                    borderColor: active ? '#3b6ef8' : 'transparent',
                    color: active ? '#3b6ef8' : 'var(--text-muted)',
                  }}
                >
                  {label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-6">
        {children}
      </main>

      <footer className="border-t py-4 text-center text-xs" style={{ borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
        © 2026 Fortunia — control financiero personal
      </footer>
    </div>
  );
}
