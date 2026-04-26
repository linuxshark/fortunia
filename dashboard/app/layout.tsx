import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Fortunia Dashboard',
  description: 'Financial expense tracking and analysis',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        <div className="min-h-screen flex flex-col bg-gray-50">
          <header className="bg-white border-b border-gray-200 sticky top-0 z-40">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
              <h1 className="text-2xl font-bold text-primary">Fortunia</h1>
              <p className="text-sm text-secondary">Financial Dashboard</p>
            </div>
          </header>

          <nav className="bg-white border-b border-gray-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex space-x-8">
                <a
                  href="/"
                  className="py-4 px-1 border-b-2 border-primary text-primary font-medium text-sm hover:text-blue-600"
                >
                  Overview
                </a>
                <a
                  href="/expenses"
                  className="py-4 px-1 border-b-2 border-transparent text-gray-600 font-medium text-sm hover:text-gray-900 hover:border-gray-300"
                >
                  Expenses
                </a>
                <a
                  href="/categories"
                  className="py-4 px-1 border-b-2 border-transparent text-gray-600 font-medium text-sm hover:text-gray-900 hover:border-gray-300"
                >
                  Categories
                </a>
              </div>
            </div>
          </nav>

          <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8">
            {children}
          </main>

          <footer className="bg-white border-t border-gray-200 mt-auto">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 text-center text-sm text-gray-600">
              <p>© 2026 Fortunia. All rights reserved.</p>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
