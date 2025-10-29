'use client';

import { useState } from 'react';
import Header from './Header';
import DashboardContent from './DashboardContent';
import type { DashboardResponse } from '../types/dashboard';

interface DashboardPageProps {
  initialData: DashboardResponse;
}

/**
 * Client wrapper component that connects the Header with DashboardContent
 * to enable export functionality in the header navigation
 */
export default function DashboardPage({ initialData }: DashboardPageProps) {
  const [exportCallbacks, setExportCallbacks] = useState<{
    onExportCSV?: () => void;
    onExportExcel?: () => void;
  }>({});
  const [isLoading, setIsLoading] = useState(false);

  return (
    <>
      <Header
        onExportCSV={exportCallbacks.onExportCSV}
        onExportExcel={exportCallbacks.onExportExcel}
        isLoading={isLoading}
      />
      <main className="page-root">
        <DashboardContent
          initialData={initialData}
          setExportCallbacks={setExportCallbacks}
          setHeaderLoading={setIsLoading}
        />
      </main>
    </>
  );
}
