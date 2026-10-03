import { useEffect, useState } from 'react';
import { systemApi } from '../api/system';
import { SystemStatus } from '../types';
import { StatCard } from '../components/StatCard';
import { StatusBadge } from '../components/StatusBadge';
import { ConfirmModal } from '../components/ConfirmModal';
import { LoadingSkeleton } from '../components/LoadingSkeleton';
import { formatUptime } from '../utils/formatters';
import { toast } from '../hooks/useToast';
import {
  Cpu,
  Database,
  Youtube,
  Wifi,
  Server,
  Layers,
  Terminal,
  Activity,
  Power,
  RefreshCw,
} from 'lucide-react';

export default function System() {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<SystemStatus | null>(null);

  // Dangerous action modal
  const [isRestartModalOpen, setIsRestartModalOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const data = await systemApi.getStatus();
      setStatus(data);
    } catch (err: any) {
      toast.error(err.message || 'Failed to load system status.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleReloadConfig = async () => {
    setActionLoading(true);
    try {
      const res = await systemApi.reload();
      toast.success(res.message || 'Configuration reloaded successfully.');
      await loadStatus();
    } catch (err: any) {
      toast.error(err.message || 'Failed to reload configuration.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleRestartBot = async () => {
    setActionLoading(true);
    try {
      const res = await systemApi.restart();
      toast.warning(res.message || 'Restart signal sent to bot.');
      setIsRestartModalOpen(false);
    } catch (err: any) {
      toast.error(err.message || 'Failed to trigger bot restart.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTestDatabase = async () => {
    try {
      toast.info('Testing database latency...');
      const res = await systemApi.testDb();
      if (res.success) {
        toast.success(`Database responsive (${res.latency_ms} ms roundtrip).`);
      } else {
        toast.error('Database query check failed.');
      }
    } catch (err: any) {
      toast.error(err.message || 'Database test failed.');
    }
  };

  const handleTestYouTube = async () => {
    try {
      toast.info('Testing YouTube monitor daemon...');
      const res = await systemApi.testYoutube();
      if (res.success) {
        toast.success(res.message || 'YouTube monitor scheduler healthy.');
      } else {
        toast.error('YouTube monitor health check degraded.');
      }
    } catch (err: any) {
      toast.error(err.message || 'YouTube test failed.');
    }
  };

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

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <Cpu className="w-7 h-7 text-[#5865F2]" />
          <span>System Diagnostics & Maintenance</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Low-level infrastructure diagnostics, daemon health, process metrics, and maintenance controls.
        </p>
      </div>

      {/* Row 1: System Telemetry Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="APP VERSION"
          value={`v${status?.system?.version || '1.0.0'}`}
          icon={Layers}
          subtitle="Production Release"
        />

        <StatCard
          title="PYTHON RUNTIME"
          value={`Python ${status?.system?.python || '3.12'}`}
          icon={Terminal}
          subtitle="Asyncio Engine"
        />

        <StatCard
          title="BOT UPTIME"
          value={formatUptime(status?.bot?.uptime)}
          icon={Activity}
          subtitle="Continuous single process"
        />

        <StatCard
          title="GATEWAY LATENCY"
          value={`${status?.bot?.latency_ms ?? 0} ms`}
          icon={Wifi}
          iconColor="text-amber-400"
          subtitle="Discord heartbeat ping"
        />
      </div>

      {/* Row 2: Subsystem Status Card */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3 flex items-center gap-2">
          <Server className="w-4 h-4 text-[#5865F2]" />
          <span>Subsystems & Health Check</span>
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-white block">Discord Client</span>
              <span className="text-[11px] text-gray-400">Gateway Shard #0</span>
            </div>
            <StatusBadge status={isBotOnline ? 'online' : 'offline'} />
          </div>

          <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-white block">SQLite + AsyncIO</span>
              <span className="text-[11px] text-gray-400">Data persistence</span>
            </div>
            <StatusBadge status={isDbConnected ? 'healthy' : 'degraded'} />
          </div>

          <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 flex items-center justify-between">
            <div>
              <span className="text-xs font-semibold text-white block">YouTube Scheduler</span>
              <span className="text-[11px] text-gray-400">Background feed poll</span>
            </div>
            <StatusBadge status={isYtHealthy ? 'healthy' : 'degraded'} />
          </div>
        </div>
      </div>

      {/* Row 3: Maintenance & Diagnostic Actions */}
      <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
        <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3">
          Maintenance Operations
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
          <button
            onClick={handleReloadConfig}
            disabled={actionLoading}
            className="flex flex-col items-center justify-center p-4 rounded-xl bg-[#0B0E14] border border-gray-800 hover:border-gray-700 hover:bg-gray-800/40 text-center transition-all group disabled:opacity-50"
          >
            <RefreshCw className="w-6 h-6 text-indigo-400 mb-2 group-hover:rotate-180 transition-transform duration-500" />
            <span className="text-xs font-bold text-white block">Reload Configuration</span>
            <span className="text-[10px] text-gray-500 mt-1">Refresh cache and policies</span>
          </button>

          <button
            onClick={handleTestDatabase}
            className="flex flex-col items-center justify-center p-4 rounded-xl bg-[#0B0E14] border border-gray-800 hover:border-gray-700 hover:bg-gray-800/40 text-center transition-all group"
          >
            <Database className="w-6 h-6 text-emerald-400 mb-2 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-bold text-white block">Test Database</span>
            <span className="text-[10px] text-gray-500 mt-1">Query roundtrip test</span>
          </button>

          <button
            onClick={handleTestYouTube}
            className="flex flex-col items-center justify-center p-4 rounded-xl bg-[#0B0E14] border border-gray-800 hover:border-gray-700 hover:bg-gray-800/40 text-center transition-all group"
          >
            <Youtube className="w-6 h-6 text-red-500 mb-2 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-bold text-white block">Test YT Monitor</span>
            <span className="text-[10px] text-gray-500 mt-1">Trigger feed heartbeat</span>
          </button>

          <button
            onClick={() => setIsRestartModalOpen(true)}
            className="flex flex-col items-center justify-center p-4 rounded-xl bg-rose-500/5 border border-rose-500/20 hover:border-rose-500/40 hover:bg-rose-500/10 text-center transition-all group"
          >
            <Power className="w-6 h-6 text-rose-400 mb-2 group-hover:scale-110 transition-transform" />
            <span className="text-xs font-bold text-rose-300 block">Restart Bot</span>
            <span className="text-[10px] text-rose-400/60 mt-1">Reconnect Discord client</span>
          </button>
        </div>
      </div>

      {/* Restart Bot Confirmation Modal */}
      <ConfirmModal
        isOpen={isRestartModalOpen}
        title="Restart Discord Bot"
        message="Are you sure you want to trigger a restart of the PB HERO bot process? The Discord client and background monitors will temporarily reconnect."
        confirmText="Restart Bot"
        isDangerous
        requiredTypedText="RESTART"
        onConfirm={handleRestartBot}
        onCancel={() => setIsRestartModalOpen(false)}
      />
    </div>
  );
}
