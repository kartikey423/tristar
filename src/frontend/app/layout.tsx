import './globals.css';
import type { Metadata } from 'next';
import Link from 'next/link';
import { SidebarNav } from '../components/Shell/SidebarNav';

export const metadata: Metadata = {
  title: 'TriStar — Canadian Tire Triangle Rewards',
  description: 'Real-time loyalty offer activation engine — Canadian Tire Corporation',
  icons: { icon: '/icon.svg' },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&display=swap"
        />
      </head>
      <body className="min-h-screen flex" suppressHydrationWarning>
        {/* Sidebar */}
        <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col bg-sidebar">
          {/* Logo */}
          <div className="flex items-center gap-3 px-5 py-5 border-b border-white/10">
            <div className="flex items-center justify-center w-8 h-8 bg-ct-red rounded">
              <span className="text-white font-bold text-xs leading-none">CT</span>
            </div>
            <div>
              <span className="text-white font-semibold text-sm tracking-tight">TriStar</span>
              <p className="text-gray-500 text-[10px] leading-tight">
                Canadian Tire Corporation
              </p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 space-y-1">
            <SidebarNav />
          </nav>

          {/* Footer */}
          <div className="px-4 py-4 border-t border-white/10">
            <div className="flex items-center gap-3">
              <span className="badge bg-amber-900/30 text-amber-400 text-[10px]">DEV</span>
              <div className="flex items-center justify-center w-7 h-7 rounded-full bg-gray-700 text-gray-300 text-xs font-medium">
                KP
              </div>
            </div>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 ml-60">
          <main className="min-h-screen p-6 max-w-[1200px]">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
