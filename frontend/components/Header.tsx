'use client';

import Image from 'next/image';

interface HeaderProps {
  onExportCSV?: () => void;
  onExportExcel?: () => void;
  isLoading?: boolean;
}

/**
 * Header component with navigation and authentication placeholder
 *
 * Features:
 * - App branding with logo/name
 * - Responsive navigation menu
 * - Export dropdown with CSV/Excel options
 * - Login/Logout placeholder buttons
 * - Mobile-friendly hamburger menu
 */
export default function Header({ onExportCSV, onExportExcel, isLoading = false }: HeaderProps) {
  return (
    <header className="app-header">
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
            <p className="brand-subtitle">Challenge Tracker</p>
          </div>
        </div>

        <nav className="header-nav">
          <div className="nav-links">
            <a href="/" className="nav-link active">Dashboard</a>

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
            <button className="btn btn-outline">Login</button>
            <button className="btn btn-primary">Sign Up</button>
          </div>
        </nav>

        {/* Mobile menu button */}
        <button className="mobile-menu-btn" aria-label="Toggle menu">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="12" x2="21" y2="12"/>
            <line x1="3" y1="6" x2="21" y2="6"/>
            <line x1="3" y1="18" x2="21" y2="18"/>
          </svg>
        </button>
      </div>
    </header>
  );
}
