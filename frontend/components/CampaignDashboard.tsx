'use client';

import { useCallback, useEffect, useMemo, useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react';

import { fetchCampaignSummary, uploadSubmissions } from '../lib/api';
import { fetchCurrentUser } from '../lib/auth';
import { toast } from '../lib/toast';
import type { CampaignSummaryResponse, SubmissionReloadSummary } from '../types/campaign';

interface CampaignDashboardProps {
  initialSummary: CampaignSummaryResponse;
  initialWeek?: string;
  isAdmin: boolean;
  setHeaderLoading?: (loading: boolean) => void;
}

type BaseSortColumn = 'user' | 'totalPoints' | 'currentRank';
type SortColumn = BaseSortColumn | `week-${number}`;
type SortDirection = 'asc' | 'desc';

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB guardrail

const RANK_DETAILS = [
  { number: 4, name: 'Secret Agent', minPoints: 750, color: 'bg-indigo-600' },
  { number: 3, name: 'Field Agent', minPoints: 500, color: 'bg-purple-600' },
  { number: 2, name: 'Agent', minPoints: 300, color: 'bg-blue-600' },
  { number: 1, name: 'Analyst', minPoints: 150, color: 'bg-sky-500' },
  { number: 0, name: 'None', minPoints: 0, color: 'bg-slate-500' },
];

interface BannerState {
  type: 'success' | 'error';
  message: string;
}

const sortComparators: Record<BaseSortColumn, (a: CampaignSummaryResponse['rows'][number], b: CampaignSummaryResponse['rows'][number]) => number> = {
  user: (a, b) => {
    const nameA = `${a.user.firstName || ''} ${a.user.lastName || ''} ${a.user.email}`.trim().toLowerCase();
    const nameB = `${b.user.firstName || ''} ${b.user.lastName || ''} ${b.user.email}`.trim().toLowerCase();
    return nameA.localeCompare(nameB);
  },
  totalPoints: (a, b) => a.totalPoints - b.totalPoints,
  currentRank: (a, b) => a.currentRank - b.currentRank,
};

function formatName(user: CampaignSummaryResponse['rows'][number]['user']) {
  const parts = [user.firstName, user.lastName].filter(Boolean);
  return parts.length > 0 ? parts.join(' ') : user.email;
}

function getVisibleWeeks(summary: CampaignSummaryResponse, selectedWeek: string) {
  if (selectedWeek === 'all') {
    return summary.weeks_present;
  }
  const parsed = Number(selectedWeek);
  return summary.weeks_present.filter((week) => week === parsed);
}

function filterRows(rows: CampaignSummaryResponse['rows'], query: string) {
  if (!query.trim()) {
    return rows;
  }
  const needle = query.trim().toLowerCase();
  return rows.filter((row) => {
    const values = [
      row.user.firstName ?? '',
      row.user.lastName ?? '',
      row.user.email,
    ]
      .join(' ')
      .toLowerCase();
    return values.includes(needle);
  });
}

export default function CampaignDashboard({ initialSummary, initialWeek = 'all', isAdmin, setHeaderLoading }: CampaignDashboardProps) {
  const [summary, setSummary] = useState<CampaignSummaryResponse>(initialSummary);
  const [selectedWeek, setSelectedWeek] = useState<string>(initialWeek);
  const [userFilter, setUserFilter] = useState('');
  const [sortColumn, setSortColumn] = useState<SortColumn>('totalPoints');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const [loading, setLoading] = useState(false);
  const [banner, setBanner] = useState<BannerState | null>(null);
  const [lastReload, setLastReload] = useState<SubmissionReloadSummary | null>(null);
  const [lastUploadAt, setLastUploadAt] = useState<Date | null>(() =>
    initialSummary.last_upload_at ? new Date(initialSummary.last_upload_at) : null,
  );
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [canAdminUpload, setCanAdminUpload] = useState(isAdmin);

  useEffect(() => {
    let active = true;
    async function refreshRole() {
      try {
        const profile = await fetchCurrentUser();
        if (active && profile.role === 'ADMIN') {
          setCanAdminUpload(true);
        }
      } catch {
        // ignore so we fall back to SSR-provided flag
      }
    }
    if (!isAdmin) {
      refreshRole();
    }
    return () => {
      active = false;
    };
  }, [isAdmin]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [isDragging, setIsDragging] = useState(false);

  const visibleWeeks = getVisibleWeeks(summary, selectedWeek);
  const filteredRows = useMemo(() => filterRows(summary.rows, userFilter), [summary.rows, userFilter]);

  const sortedRows = useMemo(() => {
    const rows = [...filteredRows];
    const comparator =
      sortColumn.startsWith('week-')
        ? (a: CampaignSummaryResponse['rows'][number], b: CampaignSummaryResponse['rows'][number]) => {
            const weekNumber = Number(sortColumn.split('-')[1]);
            const pointsA = a.pointsByWeek?.[weekNumber] ?? 0;
            const pointsB = b.pointsByWeek?.[weekNumber] ?? 0;
            return pointsA - pointsB;
          }
        : sortComparators[sortColumn as BaseSortColumn];

    rows.sort((a, b) => comparator(a, b));
    if (sortDirection === 'desc') {
      rows.reverse();
    }
    return rows;
  }, [filteredRows, sortColumn, sortDirection]);

  const handleSort = useCallback(
    (column: SortColumn) => {
      setBanner(null);
      if (column === sortColumn) {
        setSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortColumn(column);
        setSortDirection(column === 'user' ? 'asc' : 'desc');
      }
    },
    [sortColumn],
  );

  const refreshSummary = useCallback(
    async (weekValue: string) => {
      setLoading(true);
      setBanner(null);
      try {
        setHeaderLoading?.(true);
        const payload = await fetchCampaignSummary(weekValue && weekValue !== 'all' ? { week: weekValue } : {});
        setSummary(payload);
        setLastUploadAt(payload.last_upload_at ? new Date(payload.last_upload_at) : null);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Unable to load campaign summary.';
        setBanner({ type: 'error', message });
        toast.error(message);
      } finally {
        setLoading(false);
        setHeaderLoading?.(false);
      }
    },
    [setHeaderLoading],
  );

  const handleWeekChange = useCallback(
    async (value: string) => {
      setSelectedWeek(value);
      await refreshSummary(value);
    },
    [refreshSummary],
  );

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
    setBanner(null);

    const droppedFiles = event.dataTransfer.files;
    if (droppedFiles.length > 0) {
      const droppedFile = droppedFiles[0];
      if (!droppedFile.name.toLowerCase().endsWith('.csv')) {
        setBanner({ type: 'error', message: 'Only CSV files are supported.' });
        return;
      }
      if (droppedFile.size > MAX_FILE_SIZE_BYTES) {
        setBanner({ type: 'error', message: 'File exceeds the 5 MB upload limit.' });
        return;
      }
      setFile(droppedFile);
    }
  }, []);

  const handleUpload = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      setBanner(null);
      if (!file) {
        setBanner({ type: 'error', message: 'Please choose a CSV file before uploading.' });
        return;
      }
      if (!file.name.toLowerCase().endsWith('.csv')) {
        setBanner({ type: 'error', message: 'Only CSV files are supported.' });
        return;
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setBanner({ type: 'error', message: 'File exceeds the 5 MB upload limit.' });
        return;
      }

      setIsUploading(true);
      try {
        setHeaderLoading?.(true);
        const result = await uploadSubmissions(file);
        setLastReload(result);
        const message = `Processed ${result.rows_inserted} rows (${result.users_created} user${result.users_created === 1 ? '' : 's'} created, ${result.users_updated} updated).`;
        setBanner({
          type: 'success',
          message,
        });
        toast.success(message);
        await refreshSummary(selectedWeek);
        setFile(null);
      } catch (error) {
        const message = error instanceof Error ? error.message : 'Upload failed. Please try again.';
        setBanner({ type: 'error', message });
        toast.error(message || 'Upload failed. Please fix the CSV and try again.');
      } finally {
        setIsUploading(false);
        setHeaderLoading?.(false);
      }
    },
    [file, refreshSummary, selectedWeek, setHeaderLoading],
  );

  const handleFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const nextFile = event.target.files?.[0];
    setFile(nextFile ?? null);
    setBanner(null);
  }, []);

  const renderRankBadge = (rank: number) => {
    const detail = RANK_DETAILS.find((item) => item.number === rank) ?? RANK_DETAILS[RANK_DETAILS.length - 1];
    return (
      <span
        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold text-white ${detail.color}`}
      >
        {detail.name}
      </span>
    );
  };

  const resetFilters = useCallback(async () => {
    setSelectedWeek('all');
    setUserFilter('');
    await refreshSummary('all');
  }, [refreshSummary]);

  // Calculate summary statistics
  const totalUsers = summary.rows.length;
  const totalPoints = summary.rows.reduce((sum, row) => sum + row.totalPoints, 0);
  const avgPoints = totalUsers > 0 ? (totalPoints / totalUsers).toFixed(1) : '0';
  const activeWeeks = summary.weeks_present.length;

  return (
    <div className="dashboard-container" style={{ position: 'relative' }}>
      {/* Loading Overlay */}
      {loading && (
        <>
          <style dangerouslySetInnerHTML={{
            __html: `
              @keyframes dashboardSpinner {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
              }
            `
          }} />
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              backgroundColor: 'rgba(0, 0, 0, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              zIndex: 9999,
            }}
          >
            <div
              style={{
                width: '60px',
                height: '60px',
                border: '5px solid #f3f3f3',
                borderTop: '5px solid #3498db',
                borderRadius: '50%',
                animation: 'dashboardSpinner 1s linear infinite',
              }}
            />
          </div>
        </>
      )}

      {/* Collapsible Sidebar */}
      <div
        style={{
          position: 'fixed',
          bottom: '20px',
          right: sidebarCollapsed ? '-280px' : '20px',
          width: '280px',
          backgroundColor: '#ffffff',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
          zIndex: 1000,
          transition: 'right 0.3s ease-in-out',
        }}
      >
        {/* Toggle Button */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          style={{
            position: 'absolute',
            left: '-40px',
            top: '50%',
            transform: 'translateY(-50%)',
            width: '40px',
            height: '40px',
            backgroundColor: '#ffffff',
            border: '1px solid #e5e7eb',
            borderRight: 'none',
            borderTopLeftRadius: '8px',
            borderBottomLeftRadius: '8px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.2rem',
            boxShadow: '-2px 2px 4px rgba(0, 0, 0, 0.05)',
          }}
        >
          {sidebarCollapsed ? '◀' : '▶'}
        </button>

        {/* Sidebar Content */}
        <div style={{ padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem 0', fontSize: '1rem', fontWeight: '600', color: '#1f2937' }}>
            Campaign Info
          </h3>

          <div style={{ marginBottom: '1rem' }}>
            <p style={{ fontSize: '0.75rem', fontWeight: '600', color: '#6b7280', marginBottom: '0.25rem' }}>
              Rank Thresholds
            </p>
            <ul style={{ fontSize: '0.75rem', color: '#1f2937', listStyle: 'none', padding: 0, margin: 0 }}>
              {RANK_DETAILS.slice().reverse().map((rank) => (
                <li key={rank.number} style={{ display: 'flex', justifyContent: 'space-between', padding: '0.25rem 0' }}>
                  <span>{rank.name}</span>
                  <span style={{ fontWeight: '500' }}>{rank.minPoints}+ pts</span>
                </li>
              ))}
            </ul>
          </div>

          <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid #e5e7eb' }}>
            <p style={{ fontSize: '0.75rem', fontWeight: '600', color: '#6b7280', marginBottom: '0.5rem' }}>
              Quick Stats
            </p>
            <div style={{ fontSize: '0.85rem', color: '#1f2937' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span>Active Weeks:</span>
                <span style={{ fontWeight: '600' }}>{activeWeeks}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                <span>Total Users:</span>
                <span style={{ fontWeight: '600' }}>{totalUsers}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span>Avg Points:</span>
                <span style={{ fontWeight: '600' }}>{avgPoints}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Admin Upload Section */}
      {canAdminUpload && (
        <section className="section" style={{ marginBottom: '2rem' }}>
          <h2 className="section-title">Admin Upload</h2>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.25rem 0.75rem',
              borderRadius: '999px',
              backgroundColor: '#eef2ff',
              color: '#4338ca',
              fontSize: '0.85rem',
              fontWeight: 600,
              marginTop: '0.5rem',
              marginBottom: '0.5rem',
            }}
          >
            <span style={{ fontSize: '0.8rem' }}>⬆</span>
            {lastUploadAt ? `Last upload: ${lastUploadAt.toLocaleString()}` : 'No uploads yet this session'}
          </div>
          <p className="muted-text" style={{ marginBottom: '1rem' }}>
            Download the latest CSV from{' '}
            <a
              href="https://amivero.sharepoint.com/sites/MissionAIPossibleI/Lists/KahootSubmittedActivityList/AllItems.aspx"
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontWeight: '600', color: '#4338ca', textDecoration: 'underline' }}
            >
              the SharePoint list
            </a>{' '}
            and upload it to refresh points, ranks, and mission mappings.
          </p>

          <form onSubmit={handleUpload}>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              style={{
                border: isDragging ? '2px dashed #4f46e5' : '2px dashed #d1d5db',
                borderRadius: '8px',
                padding: '2rem',
                textAlign: 'center',
                backgroundColor: isDragging ? '#eef2ff' : '#f9fafb',
                transition: 'all 0.2s ease',
                cursor: 'pointer',
                marginBottom: '1rem',
              }}
              onClick={() => document.getElementById('file-input')?.click()}
            >
              <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>
                {file ? '📄' : '📁'}
              </div>
              <p style={{ fontSize: '1rem', fontWeight: '600', color: '#374151', marginBottom: '0.5rem' }}>
                {file ? file.name : 'Drag & drop your CSV file here'}
              </p>
              <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                {file ? `${(file.size / 1024).toFixed(1)} KB` : 'or click to browse'}
              </p>
              <input
                id="file-input"
                type="file"
                accept=".csv,text/csv"
                onChange={handleFileChange}
                style={{ display: 'none' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
              <button
                type="submit"
                className="filter-button"
                disabled={isUploading || !file}
                style={{ flex: 1 }}
              >
                {isUploading ? 'Uploading...' : 'Upload & Reload'}
              </button>
              {file && (
                <button
                  type="button"
                  className="filter-button secondary"
                  onClick={() => {
                    setFile(null);
                    setBanner(null);
                  }}
                  disabled={isUploading}
                >
                  Clear
                </button>
              )}
            </div>
          </form>

          {banner && (
            <div
              style={{
                marginTop: '1rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                fontSize: '0.875rem',
                border: banner.type === 'success' ? '1px solid #86efac' : '1px solid #fca5a5',
                backgroundColor: banner.type === 'success' ? '#dcfce7' : '#fee2e2',
                color: banner.type === 'success' ? '#166534' : '#991b1b',
              }}
              role="status"
              aria-live="polite"
            >
              {banner.message}
            </div>
          )}

          {lastReload && (
            <div style={{ marginTop: '1rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
              <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: '8px', backgroundColor: '#f9fafb' }}>
                <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>Rows Inserted</p>
                <p style={{ fontSize: '1.5rem', fontWeight: '600', color: '#1f2937' }}>{lastReload.rows_inserted}</p>
              </div>
              <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: '8px', backgroundColor: '#f9fafb' }}>
                <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>Users Created</p>
                <p style={{ fontSize: '1.5rem', fontWeight: '600', color: '#1f2937' }}>{lastReload.users_created}</p>
              </div>
              <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: '8px', backgroundColor: '#f9fafb' }}>
                <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>Users Updated</p>
                <p style={{ fontSize: '1.5rem', fontWeight: '600', color: '#1f2937' }}>{lastReload.users_updated}</p>
              </div>
              <div style={{ padding: '0.75rem', border: '1px solid #e5e7eb', borderRadius: '8px', backgroundColor: '#f9fafb' }}>
                <p style={{ fontSize: '0.75rem', color: '#6b7280', marginBottom: '0.25rem' }}>Missions Linked</p>
                <p style={{ fontSize: '1.5rem', fontWeight: '600', color: '#1f2937' }}>{lastReload.missions_linked}</p>
              </div>
            </div>
          )}
        </section>
      )}

      {/* Stats Grid */}
      <section className="stats-grid">
        <article className="stat-card">
          <p className="stat-label">Total Participants</p>
          <p className="stat-value">{totalUsers}</p>
          <p className="stat-sublabel">In Campaign</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Total Points</p>
          <p className="stat-value">{totalPoints.toLocaleString()}</p>
          <p className="stat-sublabel">All Users Combined</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Average Points</p>
          <p className="stat-value">{avgPoints}</p>
          <p className="stat-sublabel">Per User</p>
        </article>
        <article className="stat-card">
          <p className="stat-label">Active Weeks</p>
          <p className="stat-value">{activeWeeks}</p>
          <p className="stat-sublabel">Campaign Duration</p>
        </article>
      </section>

      {/* Filters Panel */}
      <section className="filters-panel" style={{ marginBottom: '1.5rem' }}>
        <div className="filter-group">
          <label className="filter-label" htmlFor="week-select">
            Select Week
          </label>
          <select
            id="week-select"
            className="filter-input"
            value={selectedWeek}
            onChange={(event) => handleWeekChange(event.target.value)}
            disabled={loading}
          >
            <option value="all">All Weeks</option>
            {summary.weeks_present.map((week) => (
              <option key={week} value={String(week)}>
                Week {week}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label className="filter-label" htmlFor="user-filter">
            User Filter
          </label>
          <input
            id="user-filter"
            type="text"
            placeholder="Search by name or email"
            value={userFilter}
            onChange={(event) => setUserFilter(event.target.value)}
            className="filter-input"
            disabled={loading}
          />
        </div>
        <div className="filter-group">
          <button
            className="filter-button secondary"
            onClick={resetFilters}
            disabled={loading}
            type="button"
            style={{ marginTop: '1.5rem' }}
          >
            Reset
          </button>
        </div>
      </section>

      {/* Leaderboard Section */}
      <section className="section">
        <h2 className="section-title">Campaign Leaderboard</h2>
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr className="text-left text-xs font-semibold uppercase">
                <th
                  scope="col"
                  className="cursor-pointer"
                  onClick={() => handleSort('user')}
                  style={{ cursor: 'pointer' }}
                  title="Click to sort"
                >
                  User {sortColumn === 'user' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                {visibleWeeks.map((week) => (
                  <th
                    scope="col"
                    key={week}
                    className="cursor-pointer text-center"
                    onClick={() => handleSort(`week-${week}` as SortColumn)}
                    style={{ cursor: 'pointer' }}
                    title="Click to sort"
                  >
                    Week {week} {sortColumn === `week-${week}` && (sortDirection === 'asc' ? '↑' : '↓')}
                  </th>
                ))}
                <th
                  scope="col"
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('totalPoints')}
                  style={{ cursor: 'pointer' }}
                  title="Click to sort"
                >
                  Total Points {sortColumn === 'totalPoints' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th
                  scope="col"
                  className="cursor-pointer text-right"
                  onClick={() => handleSort('currentRank')}
                  style={{ cursor: 'pointer' }}
                  title="Click to sort"
                >
                  Rank {sortColumn === 'currentRank' && (sortDirection === 'asc' ? '↑' : '↓')}
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedRows.length === 0 && (
                <tr>
                  <td colSpan={visibleWeeks.length + 3} style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>
                    No submissions match the current filters.
                  </td>
                </tr>
              )}
              {sortedRows.map((row) => (
                <tr key={row.user.email}>
                  <td>
                    <div style={{ fontWeight: '600', color: '#1f2937' }}>{formatName(row.user)}</div>
                    <div style={{ fontSize: '0.75rem', color: '#6b7280' }}>{row.user.email}</div>
                  </td>
                  {visibleWeeks.map((week) => (
                    <td key={`${row.user.email}-${week}`} style={{ textAlign: 'center', fontWeight: '500' }}>
                      {row.pointsByWeek?.[week] ?? 0}
                    </td>
                  ))}
                  <td style={{ textAlign: 'right', fontWeight: '600' }}>
                    {row.totalPoints}
                  </td>
                  <td style={{ textAlign: 'right' }}>{renderRankBadge(row.currentRank)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
