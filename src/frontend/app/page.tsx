import { Breadcrumb } from '../components/Shell/Breadcrumb';
import { fetchOffers } from '../services/hub-api';

/* Demo data for Activation Trend (last 7 days) */
const ACTIVATION_TREND = [
  { day: 'Mon', count: 14 },
  { day: 'Tue', count: 22 },
  { day: 'Wed', count: 18 },
  { day: 'Thu', count: 31 },
  { day: 'Fri', count: 27 },
  { day: 'Sat', count: 9 },
  { day: 'Sun', count: 5 },
];
const TREND_MAX = Math.max(...ACTIVATION_TREND.map((d) => d.count));

/* Demo data for Security Audit Logs */
const AUDIT_LOGS = [
  {
    id: 1,
    message: 'Offer demo-winter-001 approved by marketer-1',
    timestamp: '2026-03-29 14:32',
    severity: 'success' as const,
  },
  {
    id: 2,
    message: 'Fraud check passed for offer demo-spring-002',
    timestamp: '2026-03-29 14:28',
    severity: 'success' as const,
  },
  {
    id: 3,
    message: 'JWT token validated for marketer-1',
    timestamp: '2026-03-29 14:25',
    severity: 'info' as const,
  },
  {
    id: 4,
    message: 'Rate limit check: M001 within threshold',
    timestamp: '2026-03-29 14:20',
    severity: 'info' as const,
  },
  {
    id: 5,
    message: 'Suspicious frequency pattern detected for M047',
    timestamp: '2026-03-29 14:12',
    severity: 'warning' as const,
  },
  {
    id: 6,
    message: 'Offer demo-flash-003 blocked — critical risk flag',
    timestamp: '2026-03-29 13:58',
    severity: 'warning' as const,
  },
];

function formatRelativeTime(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHr < 24) return `${diffHr}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

export default async function DashboardPage() {
  let offers: Awaited<ReturnType<typeof fetchOffers>>['offers'] = [];
  try {
    const result = await fetchOffers({});
    offers = result.offers;
  } catch {
    // Graceful degradation — show empty state
  }

  const activeCount = offers.filter((o) => o.status === 'active').length;
  const approvedCount = offers.filter((o) => o.status === 'approved').length;
  const draftCount = offers.filter((o) => o.status === 'draft').length;
  const expiredCount = offers.filter((o) => o.status === 'expired').length;

  const totalActivations = ACTIVATION_TREND.reduce((sum, d) => sum + d.count, 0);
  const todayActivations = ACTIVATION_TREND[ACTIVATION_TREND.length - 1].count;
  const avgActivations = Math.round(totalActivations / ACTIVATION_TREND.length);
  const maxActivations = TREND_MAX;

  return (
    <>
      <Breadcrumb items={['TriStar', 'Dashboard']} />

      <h1 className="text-headline text-gray-900 mb-6">Dashboard</h1>

      {/* KPI Row */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        <div className="kpi-card">
          <p className="kpi-label">Active Offers</p>
          <p className="kpi-value text-emerald-600">{activeCount}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Pending Approval</p>
          <p className="kpi-value text-amber-600">{approvedCount}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Drafts</p>
          <p className="kpi-value text-gray-600">{draftCount}</p>
        </div>
        <div className="kpi-card">
          <p className="kpi-label">Total Offers</p>
          <p className="kpi-value">{offers.length}</p>
        </div>
      </div>

      {/* Recent Offers Table */}
      <div className="card p-5">
        <h2 className="text-title text-gray-900 mb-4">Recent Offers</h2>
        {offers.length === 0 ? (
          <p className="text-sm text-gray-500 py-8 text-center">
            No offers yet. Create your first offer in the Designer.
          </p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Offer ID</th>
                <th>Objective</th>
                <th>Trigger</th>
                <th>Score</th>
                <th>Risk</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {offers.slice(0, 8).map((offer) => {
                const score = Math.round(
                  (offer.kpis?.expected_redemption_rate ?? 0) * 100,
                );
                return (
                  <tr key={offer.offer_id}>
                    <td>
                      <span className="flex items-center gap-2">
                        <span className={`status-dot status-dot-${offer.status}`} />
                        <span className="capitalize text-sm">{offer.status}</span>
                      </span>
                    </td>
                    <td>
                      <code className="text-xs text-gray-600 font-mono bg-gray-50 px-1.5 py-0.5 rounded">
                        {offer.offer_id}
                      </code>
                    </td>
                    <td className="text-sm text-gray-900 max-w-xs truncate">
                      {offer.objective}
                    </td>
                    <td>
                      <span className="badge badge-neutral">
                        {offer.trigger_type === 'purchase_triggered' ? 'Purchase' : 'Marketer'}
                      </span>
                    </td>
                    <td>
                      <span
                        className={`text-sm font-medium ${
                          score >= 70
                            ? 'text-emerald-600'
                            : score >= 40
                              ? 'text-amber-600'
                              : 'text-gray-500'
                        }`}
                      >
                        {score}%
                      </span>
                    </td>
                    <td>
                      <RiskBadge severity={offer.risk_flags.severity} />
                    </td>
                    <td>
                      <span className="text-xs text-gray-500 whitespace-nowrap">
                        {formatRelativeTime(offer.created_at)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {/* Activation Trend + Security Audit Logs */}
      <div className="grid grid-cols-2 gap-4 mt-6">
        {/* Activation Trend */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-title text-gray-900">Activation Trend</h2>
            <span className="text-xs text-gray-500">Last 7 days</span>
          </div>
          {/* Activation KPI mini-stats */}
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="rounded-md bg-blue-50/60 border border-blue-100 px-3 py-2 text-center">
              <p className="text-[10px] uppercase tracking-wider text-blue-500 font-medium">Today</p>
              <p className="text-xl font-bold text-blue-800 mt-0.5">{todayActivations}</p>
            </div>
            <div className="rounded-md bg-emerald-50/60 border border-emerald-100 px-3 py-2 text-center">
              <p className="text-[10px] uppercase tracking-wider text-emerald-500 font-medium">Daily Avg</p>
              <p className="text-xl font-bold text-emerald-800 mt-0.5">{avgActivations}</p>
            </div>
            <div className="rounded-md bg-amber-50/60 border border-amber-100 px-3 py-2 text-center">
              <p className="text-[10px] uppercase tracking-wider text-amber-500 font-medium">Peak</p>
              <p className="text-xl font-bold text-amber-800 mt-0.5">{maxActivations}</p>
            </div>
          </div>
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-[16px] text-emerald-600" aria-hidden="true">
              trending_up
            </span>
            <span className="text-sm text-gray-600">
              <span className="font-semibold text-gray-900">{totalActivations}</span> total activations
            </span>
          </div>
          <div className="flex items-end gap-2 h-32">
            {ACTIVATION_TREND.map((d) => {
              const heightPct = TREND_MAX > 0 ? (d.count / TREND_MAX) * 100 : 0;
              return (
                <div key={d.day} className="flex-1 flex flex-col items-center gap-1">
                  <span className="text-xs font-medium text-gray-700">{d.count}</span>
                  <div className="w-full flex items-end" style={{ height: '80px' }}>
                    <div
                      className="w-full rounded-t bg-blue-500 hover:bg-blue-600 transition-colors"
                      style={{ height: `${heightPct}%`, minHeight: '4px' }}
                    />
                  </div>
                  <span className="text-xs text-gray-500">{d.day}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Security Audit Logs */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-title text-gray-900">Security Audit Logs</h2>
            <span className="material-symbols-outlined text-[16px] text-gray-400" aria-hidden="true">
              shield
            </span>
          </div>
          <div className="space-y-0">
            {AUDIT_LOGS.map((log) => (
              <div
                key={log.id}
                className="flex items-start gap-3 py-2.5 border-b border-gray-50 last:border-0"
              >
                <AuditIcon severity={log.severity} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-800 leading-snug">{log.message}</p>
                  <p className="text-xs text-gray-400 mt-0.5">{log.timestamp}</p>
                </div>
                <SeverityBadge severity={log.severity} />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Offer Distribution + System Health */}
      <div className="grid grid-cols-2 gap-4 mt-6">
        <div className="card p-5">
          <h2 className="text-title text-gray-900 mb-4">Offer Distribution</h2>
          <div className="space-y-3">
            <StatusBar label="Active" count={activeCount} total={offers.length} color="bg-emerald-500" />
            <StatusBar label="Approved" count={approvedCount} total={offers.length} color="bg-blue-500" />
            <StatusBar label="Draft" count={draftCount} total={offers.length} color="bg-gray-400" />
            <StatusBar label="Expired" count={expiredCount} total={offers.length} color="bg-red-400" />
          </div>
        </div>
        <div className="card p-5">
          <h2 className="text-title text-gray-900 mb-4">System Health</h2>
          <div className="space-y-3">
            <HealthRow label="Designer API" status="Operational" />
            <HealthRow label="Hub Store" status="Operational" />
            <HealthRow label="Scout Engine" status="Operational" />
          </div>
        </div>
      </div>
    </>
  );
}

/* ---------- Helper Components ---------- */

function RiskBadge({ severity }: { severity: string }) {
  const cls =
    severity === 'critical' ? 'badge-danger' :
    severity === 'medium' ? 'badge-warning' :
    'badge-success';
  return <span className={`badge ${cls} capitalize`}>{severity}</span>;
}

function StatusBar({ label, count, total, color }: { label: string; count: number; total: number; color: string }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-1">
        <span className="text-gray-600">{label}</span>
        <span className="font-medium text-gray-900">{count}</span>
      </div>
      <div className="h-1.5 rounded-full bg-gray-100">
        <div className={`h-1.5 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function HealthRow({ label, status }: { label: string; status: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
      <span className="text-sm text-gray-700">{label}</span>
      <span className="flex items-center gap-1.5 text-sm">
        <span className="status-dot bg-emerald-500" />
        <span className="text-emerald-700">{status}</span>
      </span>
    </div>
  );
}

function AuditIcon({ severity }: { severity: 'success' | 'info' | 'warning' }) {
  const config = {
    success: { icon: 'check_circle', color: 'text-emerald-500' },
    info: { icon: 'info', color: 'text-blue-500' },
    warning: { icon: 'warning', color: 'text-amber-500' },
  };
  const { icon, color } = config[severity];
  return (
    <span className={`material-symbols-outlined text-[16px] mt-0.5 ${color}`} aria-hidden="true">
      {icon}
    </span>
  );
}

function SeverityBadge({ severity }: { severity: 'success' | 'info' | 'warning' }) {
  const cls = {
    success: 'badge-success',
    info: 'badge-info',
    warning: 'badge-warning',
  }[severity];
  const label = {
    success: 'OK',
    info: 'Info',
    warning: 'Warn',
  }[severity];
  return <span className={`badge ${cls} shrink-0`}>{label}</span>;
}
