'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: 'dashboard' },
  { href: '/designer', label: 'Designer', icon: 'auto_awesome' },
  { href: '/hub', label: 'Hub', icon: 'hub' },
  { href: '/scout', label: 'Scout', icon: 'track_changes' },
];

export function SidebarNav() {
  const pathname = usePathname();

  return (
    <>
      {NAV_ITEMS.map(({ href, label, icon }) => {
        const isActive =
          href === '/' ? pathname === '/' : pathname.startsWith(href);

        return (
          <Link
            key={href}
            href={href}
            className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
          >
            <span
              className="material-symbols-outlined text-[20px]"
              aria-hidden="true"
            >
              {icon}
            </span>
            {label}
          </Link>
        );
      })}
    </>
  );
}
