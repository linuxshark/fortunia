import type { Metadata } from 'next';
import './globals.css';
import { ThemeProvider } from './components/ThemeProvider';
import AppShell from './components/AppShell';

export const metadata: Metadata = {
  title: 'Fortunia',
  description: 'Control financiero personal',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
