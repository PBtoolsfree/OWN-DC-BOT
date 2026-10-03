import { useEffect, useState } from 'react';
import { systemApi } from '../api/system';
import { moderationApi } from '../api/moderation';
import { SystemStatus, SystemOverview, AuditLogItem, BlockedMessage, ModerationCase } from '../types';
import { StatCard } from '../components/StatCard';
import { StatusBadge } from '../components/StatusBadge';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { formatUptime, formatRelativeTime } from '../utils/formatters';
import {
  Bot,
  Wifi,
  Database,
  Youtube,
  Clock,
  Activity,
  ShieldAlert,
  Flame,
  Shield,
  Layers,
} from 'lucide-react';

export default function Overview() {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [blocked, setBlocked] = useState<BlockedMessage[]>([]);
  const [cases, setCases] = useState<ModerationCase[]>([]);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        const [statusData, overviewData, logsData, blockedData, casesData] = await Promise.allSettled([
          systemApi.getStatus(),
          systemApi.getOverview(),
          systemApi.getAuditLogs(10),
          moderationApi.getBlocked(10),
          moderationApi.getCases(10),
        ]);

        if (!isMounted) return;

        if (statusData.status === 'fulfilled') setStatus(statusData.value);
        if (overviewData.status === 'fulfilled') setOverview(overviewData.value);
        if (logsData.status === 'fulfilled') setAuditLogs(logsData.value);
        if (blockedData.status === 'fulfilled') setBlocked(blockedData.value);
        if (casesData.status === 'fulfilled') setCases(casesData.value);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-800 animate-pulse rounded" />
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  const isBotOnline = status?.bot?.connected ?? false;
  const isDbConnected = status?.database?.connected ?? false;
  const isYtHealthy = status?.youtube?.healthy ?? false;
  const uptimeStr = formatUptime(status?.bot?.uptime);
  const latencyStr = `${status?.bot?.latency_ms ?? 0} ms`;

  // Aggregate recent activities
  const recentActivities: Array<{
    id: string;
    type: 'youtube' | 'blocked' | 'case' | 'policy' | 'system';
    title: string;
    details: string;
    timestamp: string;
  }> = [];

  cases.slice(0, 5).forEach((c) => {
    recentActivities.push({
      id: `case-${c.case_number}`,
      type: 'case',
      title: `Moderation Case #${c.case_number} (${c.action.toUpperCase()})`,
      details: `Target: ${c.target_username} • Reason: ${c.reason || 'No reason'}`,
      timestamp: c.created_at,
    });
  });

  blocked.slice(0, 5).forEach((b) => {
    recentActivities.push({
      id: `blocked-${b.id}`,
      type: 'blocked',
      title: `Blocked Message (${b.rule || 'Filter'})`,
      details: `User: ${b.username} • Reason: ${b.reason}`,
      timestamp: b.created_at,
    });
  });

  auditLogs.slice(0, 5).forEach((l) => {
    if (l.action.includes('policy') || l.action.includes('youtube')) {
      recentActivities.push({
        id: `audit-${l.id}`,
        type: l.action.includes('policy') ? 'policy' : 'youtube',
        title: l.action.replace(/_/g, ' ').toUpperCase(),
        details: `Actor: ${l.actor} ${l.target ? `• Target: ${l.target}` : ''}`,
        timestamp: l.created_at,
      });
    }
  });

  // Sort by timestamp desc
  recentActivities.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight">System Overview</h1>
        <p className="text-xs text-gray-400 mt-1">
          Real-time diagnostics and moderation telemetry for single configured Discord guild.
        </p>
      </div>

      {/* Row 1: Core Bot Health Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard
          title="BOT STATUS"
          value={isBotOnline ? 'ONLINE' : 'OFFLINE'}
          icon={Bot}
          badge={<StatusBadge status={isBotOnline ? 'online' : 'offline'} />}
        />

        <StatCard
          title="DISCORD"
          value={isBotOnline ? 'Connected' : 'Disconnected'}
          icon={Wifi}
          badge={<StatusBadge status={isBotOnline ? 'connected' : 'disconnected'} />}
        />

        <StatCard
          title="DATABASE"
          value={isDbConnected ? 'Healthy' : 'Degraded'}
          icon={Database}
          badge={<StatusBadge status={isDbConnected ? 'healthy' : 'degraded'} />}
        />

        <StatCard
          title="YT MONITOR"
          value={isYtHealthy ? 'Healthy' : 'Degraded'}
          icon={Youtube}
          iconColor="text-red-500"
          badge={<StatusBadge status={isYtHealthy ? 'healthy' : 'degraded'} />}
        />

        <StatCard
          title="UPTIME"
          value={uptimeStr}
          icon={Clock}
          iconColor="text-indigo-400"
        />

        <StatCard
          title="LATENCY"
          value={latencyStr}
          icon={Activity}
          iconColor="text-amber-400"
        />
      </div>

      {/* Row 2: Statistics Sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* YouTube Statistics */}
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-red-500/10 text-red-500">
                <Youtube className="w-5 h-5" />
              </div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                YouTube Statistics
              </h2>
            </div>
            <StatusBadge status="online" label="RSS POLLING" />
          </div>

          <div className="grid grid-cols-3 gap-4 pt-2">
            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4">
              <span className="text-[11px] font-semibold text-gray-400 block mb-1">
                Monitored Channels
              </span>
              <span className="text-2xl font-black text-white">
                {overview?.youtube_channels ?? 0}
              </span>
              <span className="text-[10px] text-gray-500 block mt-1">
                {overview?.youtube_enabled ?? 0} active
              </span>
            </div>

            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4">
              <span className="text-[11px] font-semibold text-gray-400 block mb-1">
                Notifications Today
              </span>
              <span className="text-2xl font-black text-emerald-400">
                {overview?.notifications_today ?? 0}
              </span>
              <span className="text-[10px] text-gray-500 block mt-1">Videos & Lives</span>
            </div>

            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4">
              <span className="text-[11px] font-semibold text-gray-400 block mb-1">
                Last Notification
              </span>
              <span className="text-xs font-bold text-white block mt-2">
                {auditLogs.find((l) => l.action.includes('youtube'))
                  ? formatRelativeTime(auditLogs.find((l) => l.action.includes('youtube'))?.created_at)
                  : 'None today'}
              </span>
            </div>
          </div>
        </div>

        {/* Moderation Statistics */}
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-gray-800 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-2 rounded-lg bg-[#5865F2]/10 text-[#5865F2]">
                <Shield className="w-5 h-5" />
              </div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Moderation Statistics
              </h2>
            </div>
            <StatusBadge status="online" label="ENGINE ACTIVE" />
          </div>

          <div className="grid grid-cols-4 gap-3 pt-2">
            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3 text-center">
              <span className="text-[10px] font-semibold text-gray-400 block mb-1 uppercase">
                Blocked Msg
              </span>
              <span className="text-xl font-black text-rose-400">
                {overview?.blocked_messages_today ?? 0}
              </span>
            </div>

            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3 text-center">
              <span className="text-[10px] font-semibold text-gray-400 block mb-1 uppercase">
                Blocked Links
              </span>
              <span className="text-xl font-black text-amber-400">
                {blocked.filter((b) => b.rule?.includes('link')).length}
              </span>
            </div>

            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3 text-center">
              <span className="text-[10px] font-semibold text-gray-400 block mb-1 uppercase">
                Attachments
              </span>
              <span className="text-xl font-black text-indigo-400">
                {blocked.filter((b) => b.rule?.includes('attachment') || b.rule?.includes('file')).length}
              </span>
            </div>

            <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-3 text-center">
              <span className="text-[10px] font-semibold text-gray-400 block mb-1 uppercase">
                Mod Cases
              </span>
              <span className="text-xl font-black text-white">
                {overview?.moderation_cases_today ?? 0}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Row 3: Recent Activity Feed */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div className="flex items-center gap-2">
            <Flame className="w-5 h-5 text-amber-400" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">
              Recent Activity Feed
            </h2>
          </div>
          <span className="text-xs text-gray-500">Live event stream</span>
        </div>

        {recentActivities.length === 0 ? (
          <div className="py-8 text-center text-xs text-gray-500">No recent activity detected.</div>
        ) : (
          <div className="divide-y divide-gray-800/60">
            {recentActivities.map((act) => (
              <div
                key={act.id}
                className="py-3 px-2 flex items-center justify-between hover:bg-gray-800/30 transition-colors rounded-lg text-xs"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2 rounded-lg bg-[#0B0E14] border border-gray-800 text-gray-400 shrink-0">
                    {act.type === 'youtube' && <Youtube className="w-4 h-4 text-red-500" />}
                    {act.type === 'blocked' && <ShieldAlert className="w-4 h-4 text-rose-400" />}
                    {act.type === 'case' && <Shield className="w-4 h-4 text-[#5865F2]" />}
                    {act.type === 'policy' && <Layers className="w-4 h-4 text-emerald-400" />}
                  </div>
                  <div className="min-w-0">
                    <span className="font-semibold text-white block truncate">{act.title}</span>
                    <span className="text-gray-400 text-[11px] block truncate">{act.details}</span>
                  </div>
                </div>

                <span className="text-gray-500 text-[11px] font-mono shrink-0 pl-4">
                  {formatRelativeTime(act.timestamp)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
