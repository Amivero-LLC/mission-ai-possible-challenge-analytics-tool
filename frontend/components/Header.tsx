'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

import { fetchCurrentUser, logout } from '../lib/auth';
import { toast } from '../lib/toast';
import type { AuthUser } from '../types/auth';

interface HeaderProps {
  onExportCSV?: () => void;
  onExportExcel?: () => void;
  isLoading?: boolean;
}

/**
 * Primary application header with authenticated navigation.
 *
 * Highlights:
 * - Renders brand, dashboard nav, and the admin dropdown when available.
 * - Surfaces export controls provided by the dashboard content layer.
 * - Shows the signed-in user with a working sign-out action (or redirect to login).
 * - Adapts styling on admin routes to reinforce elevated privileges.
 */
export default function Header({ onExportCSV, onExportExcel, isLoading = false }: HeaderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchString = searchParams.toString();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const isAdminRoute = pathname?.startsWith('/admin') ?? false;
  const canAccessAdmin = user?.role === 'ADMIN' || isAdminRoute;

  const primaryNavItems = useMemo(
    () => [
      {
        href: '/campaign',
        label: 'Campaign Dashboard',
        isActive: pathname === '/campaign',
      },
      {
        href: '/',
        label: 'Challenge Dashboard',
        isActive: pathname === '/',
      },      
    ],
    [pathname],
  );

  const adminLinks = useMemo(() => {
    const path = pathname ?? '';
    return [
      {
        href: '/admin/config',
        label: 'Configuration',
        isActive: path === '/admin' || path.startsWith('/admin/config'),
      },
      {
        href: '/admin/users',
        label: 'User approvals',
        isActive: path.startsWith('/admin/users'),
      },
      {
        href: '/admin/models',
        label: 'Model admin',
        isActive: path.startsWith('/admin/models'),
      },
      {
        href: '/admin/audit',
        label: 'Audit trail',
        isActive: path.startsWith('/admin/audit'),
      },
    ];
  }, [pathname]);
  const adminMenuActive = isAdminRoute;
  const headerClassName = `app-header${isAdminRoute ? ' app-header--admin' : ''}`;
  const userNameClass = `font-semibold ${isAdminRoute ? 'text-slate-100' : 'text-slate-900'}`;
  const userRoleClass = `text-xs ${isAdminRoute ? 'text-slate-300' : 'text-slate-500'}`;

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const profile = await fetchCurrentUser();
        if (active) {
          setUser(profile);
          if (typeof window !== 'undefined') {
            const marker = sessionStorage.getItem('maip_auth_notice');
            if (marker === 'signed_in') {
              toast.success('Signed in successfully.');
              sessionStorage.removeItem('maip_auth_notice');
            } else if (marker === 'logged_out') {
              toast.info('Signed out successfully.');
              sessionStorage.removeItem('maip_auth_notice');
            }
          }
        }
      } catch (error) {
        if (active) {
          const currentPath = pathname ?? '/';
          const target = searchString ? `${currentPath}?${searchString}` : currentPath;
          const params = new URLSearchParams();
          params.set('reason', 'expired');
          if (!target.startsWith('/auth/')) {
            params.set('redirect', target || '/');
          }
          if (typeof window !== 'undefined') {
            sessionStorage.setItem('maip_post_auth_redirect', target || '/');
          }
          router.push(`/auth/login?${params.toString()}`);
        }
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [pathname, router, searchString]);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  async function handleLogout() {
    try {
      setIsLoggingOut(true);
      await logout();

      // Clear localStorage tokens (for cross-domain auth)
      if (typeof window !== 'undefined') {
        localStorage.removeItem('maip_access_token');
        localStorage.removeItem('maip_token_expires');
      }

      const currentPath = pathname ?? '/';
      const target = searchString ? `${currentPath}?${searchString}` : currentPath;
      const params = new URLSearchParams();
      params.set('status', 'logged_out');
      if (!target.startsWith('/auth/')) {
        params.set('redirect', target || '/');
      }
      if (typeof window !== 'undefined') {
        sessionStorage.setItem('maip_post_auth_redirect', target || '/');
        sessionStorage.setItem('maip_auth_notice', 'logged_out');
      }
      router.push(`/auth/login?${params.toString()}`);
    } finally {
      setIsLoggingOut(false);
    }
  }

  const closeMobileMenu = () => setIsMobileMenuOpen(false);
  const mobileMenuClassName = [
    'mobile-menu',
    isMobileMenuOpen ? 'open' : '',
    isAdminRoute ? 'mobile-menu--admin' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <>
      <header className={headerClassName}>
        <div className="header-container">
        <div className="header-brand">
          <div className="brand-logo">
            <Image
              src="/icon-32x32.png"
              alt="Mission:AI Possible Logo"
              width={32}
              height={32}
              priority
            />
          </div>
          <div className="brand-text">
            <h1 className="brand-title">Mission:AI Possible</h1>
            <p className="brand-subtitle">Campaign Tracker</p>
          </div>
        </div>

        <nav className="header-nav">
          <div className="nav-links">
            {primaryNavItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`nav-link${item.isActive ? ' active' : ''}`}
              >
                {item.label}
              </Link>
            ))}

            {canAccessAdmin && (
              <div className="nav-dropdown">
                <button
                  type="button"
                  className={`nav-link nav-link-button${adminMenuActive ? ' active' : ''}`}
                >
                  Admin
                  <svg
                    aria-hidden="true"
                    width="12"
                    height="12"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </button>
                <div className="nav-dropdown-menu">
                  <div className="nav-dropdown-panel">
                    {adminLinks.map((link) => (
                      <Link
                        key={link.href}
                        href={link.href}
                        className={`nav-dropdown-link${link.isActive ? ' active' : ''}`}
                      >
                        {link.label}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Export Dropdown */}
            {onExportCSV && onExportExcel && (
              <div
                style={{
                  position: "relative",
                  display: "inline-block",
                }}
                onMouseEnter={(e) => {
                  const dropdown = e.currentTarget.querySelector('[data-export-dropdown]') as HTMLElement;
                  if (dropdown) dropdown.style.display = 'block';
                }}
                onMouseLeave={(e) => {
                  const dropdown = e.currentTarget.querySelector('[data-export-dropdown]') as HTMLElement;
                  if (dropdown) dropdown.style.display = 'none';
                }}
              >
                <button
                  className="nav-link"
                  style={{
                    background: "transparent",
                    border: "none",
                    cursor: "pointer",
                  }}
                  disabled={isLoading}
                  type="button"
                >
                  📥 Export
                </button>

                <div
                  data-export-dropdown
                  style={{
                    display: "none",
                    position: "absolute",
                    left: 0,
                    top: "100%",
                    paddingTop: "0.25rem",
                    backgroundColor: "transparent",
                    minWidth: "150px",
                    zIndex: 1000,
                  }}
                >
                  <div style={{
                    backgroundColor: "white",
                    border: "1px solid #e5e7eb",
                    borderRadius: "8px",
                    boxShadow: "0 4px 6px rgba(0, 0, 0, 0.1)",
                  }}>
                  <button
                    onClick={onExportCSV}
                    disabled={isLoading}
                    type="button"
                    style={{
                      width: "100%",
                      padding: "0.75rem 1rem",
                      textAlign: "left",
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      fontSize: "0.9rem",
                      fontWeight: "500",
                      color: "#374151",
                      borderRadius: "8px 8px 0 0",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = "#f3f4f6";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = "transparent";
                    }}
                  >
                    📄 CSV
                  </button>
                  <button
                    onClick={onExportExcel}
                    disabled={isLoading}
                    type="button"
                    style={{
                      width: "100%",
                      padding: "0.75rem 1rem",
                      textAlign: "left",
                      border: "none",
                      background: "transparent",
                      cursor: "pointer",
                      fontSize: "0.9rem",
                      fontWeight: "500",
                      color: "#374151",
                      borderRadius: "0 0 8px 8px",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = "#f3f4f6";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = "transparent";
                    }}
                  >
                    📊 Excel
                  </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="header-actions">
            {user ? (
              <div className="flex items-center gap-3">
                <div className="text-right text-sm">
                  <p className={userNameClass}>{user.username ?? user.email}</p>
                  <p className={userRoleClass}>{user.role}</p>
                </div>
                <button
                  className="btn btn-outline"
                  type="button"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                >
                  {isLoggingOut ? 'Signing out...' : 'Sign out'}
                </button>
              </div>
            ) : (
              <button className="btn btn-outline" type="button" onClick={() => router.push('/auth/login')}>
                Sign in
              </button>
            )}
          </div>
        </nav>

        {/* Mobile menu button */}
        <button
          className="mobile-menu-btn"
          aria-label="Toggle menu"
          aria-expanded={isMobileMenuOpen}
          aria-controls="app-mobile-menu"
          onClick={() => setIsMobileMenuOpen((prev) => !prev)}
        >
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
      </div>
    </header>
      <div id="app-mobile-menu" className={mobileMenuClassName}>
        <div className="mobile-menu-section">
          {primaryNavItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`mobile-menu-link${item.isActive ? ' active' : ''}`}
              onClick={closeMobileMenu}
            >
              {item.label}
            </Link>
          ))}
        </div>
        {canAccessAdmin && (
          <div className="mobile-menu-section">
            <p className="mobile-menu-section-title">Admin</p>
            {adminLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`mobile-menu-link${link.isActive ? ' active' : ''}`}
                onClick={closeMobileMenu}
              >
                {link.label}
              </Link>
            ))}
          </div>
        )}
        {onExportCSV && onExportExcel && (
          <div className="mobile-menu-section">
            <p className="mobile-menu-section-title">Exports</p>
            <button
              type="button"
              className="mobile-menu-link mobile-menu-link--button"
              onClick={() => {
                onExportCSV();
                closeMobileMenu();
              }}
              disabled={isLoading}
            >
              📄 CSV
            </button>
            <button
              type="button"
              className="mobile-menu-link mobile-menu-link--button"
              onClick={() => {
                onExportExcel();
                closeMobileMenu();
              }}
              disabled={isLoading}
            >
              📊 Excel
            </button>
          </div>
        )}
        <div className="mobile-menu-actions">
          {user ? (
            <>
              <div className="mobile-user">
                <p className={userNameClass}>{user.username ?? user.email}</p>
                <p className={userRoleClass}>{user.role}</p>
              </div>
              <button
                className="btn btn-outline"
                type="button"
                onClick={() => {
                  closeMobileMenu();
                  handleLogout();
                }}
                disabled={isLoggingOut}
              >
                {isLoggingOut ? 'Signing out...' : 'Sign out'}
              </button>
            </>
          ) : (
            <button
              className="btn btn-outline"
              type="button"
              onClick={() => {
                closeMobileMenu();
                router.push('/auth/login');
              }}
            >
              Sign in
            </button>
          )}
        </div>
      </div>
    </>
  );
}
