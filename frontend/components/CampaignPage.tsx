'use client';

import { useState } from 'react';
import Header from './Header';
import CampaignDashboard from './CampaignDashboard';
import type { CampaignSummaryResponse } from '../types/campaign';

interface CampaignPageProps {
  initialSummary?: CampaignSummaryResponse | null;
  initialWeek?: string;
  isAdmin: boolean;
}

/**
 * Client wrapper component that connects the Header with CampaignDashboard
 * to enable consistent navigation and layout
 */
export default function CampaignPage({ initialSummary = null, initialWeek = 'all', isAdmin }: CampaignPageProps) {
  const [isLoading, setIsLoading] = useState(false);

  return (
    <>
      <Header isLoading={isLoading} />
      <main className="page-root">
        <CampaignDashboard
          initialSummary={initialSummary}
          initialWeek={initialWeek}
          isAdmin={isAdmin}
          setHeaderLoading={setIsLoading}
        />
      </main>
    </>
  );
}
