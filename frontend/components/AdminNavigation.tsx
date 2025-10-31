'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const ADMIN_LINKS = [
  { href: '/admin/config', label: 'Configuration' },
  { href: '/admin/users', label: 'User approvals' },
  { href: '/admin/audit', label: 'Audit trail' },
];

/**
 * Pills-style navigation used across admin pages to provide quick links
 * to configuration, user approvals, and audit history.
 */
export default function AdminNavigation() {
  const pathname = usePathname();

  return (
    <nav className="flex flex-wrap items-center gap-2">
      {ADMIN_LINKS.map((link) => {
        const isActive = pathname === link.href || pathname.startsWith(`${link.href}/`);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={`inline-flex items-center rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
              isActive
                ? 'border-indigo-200 bg-indigo-50 text-indigo-700 shadow-sm'
                : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200 hover:bg-slate-50 hover:text-indigo-600'
            }`}
            aria-current={isActive ? 'page' : undefined}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
