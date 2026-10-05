import { useState, useEffect, useCallback } from 'react';
import {
  Link2,
  Users,
  UserCheck,
  TrendingUp,
  AlertCircle,
  Search,
  RefreshCw,
  Copy,
  Check,
  Trash2,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
  X,
  User,
  Activity,
  Radio,
  Sparkles,
  RotateCcw,
  Send,
  Palette,
  CheckCircle2,
  Hash,
  Sliders,
} from 'lucide-react';
import { invitesApi } from '../api/invites';
import {
  DiscordTrackedInvite,
  InviteActivitySettings,
  InviteChannelOption,
  InviteJoinRecord,
  InviteLeaderboardEntry,
  InviteOverviewStats,
  InviteTrackerHealth,
  UserInviteProfile,
} from '../types';
import { toast } from '../hooks/useToast';
import { LoadingSkeleton } from '../components/LoadingSkeleton';

export default function InviteTracking() {
  const [activeTab, setActiveTab] = useState<'invites' | 'joins' | 'activity' | 'diagnostics'>('invites');
  const [timeframe, setTimeframe] = useState<'today' | '7d' | '30d' | 'all'>('all');
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);

  // Overview stats & health
  const [stats, setStats] = useState<InviteOverviewStats | null>(null);
  const [health, setHealth] = useState<InviteTrackerHealth | null>(null);
  const [leaderboard, setLeaderboard] = useState<InviteLeaderboardEntry[]>([]);

  // Activity Log & Channel settings
  const [activitySettings, setActivitySettings] = useState<InviteActivitySettings | null>(null);
  const [activityChannels, setActivityChannels] = useState<InviteChannelOption[]>([]);
  const [loadingActivity, setLoadingActivity] = useState(false);
  const [savingActivity, setSavingActivity] = useState(false);
  const [testingActivity, setTestingActivity] = useState(false);
  const [activityForm, setActivityForm] = useState({
    enabled: false,
    channel_id: '',
    title_template: '🎉 NEW MEMBER INVITED',
    description_template: '{inviter_mention} invited {member_mention}',
    color_hex: '#5865F2',
    log_unknown: true,
    log_vanity: true,
    log_created: false,
    log_revoked: false,
  });

  // Invites list state
  const [invites, setInvites] = useState<DiscordTrackedInvite[]>([]);
  const [invitesTotal, setInvitesTotal] = useState(0);
  const [invitesPage, setInvitesPage] = useState(1);
  const [invitesTotalPages, setInvitesTotalPages] = useState(1);
  const [inviteStatusFilter, setInviteStatusFilter] = useState<string>('ALL');
  const [inviteSearch, setInviteSearch] = useState<string>('');

  // Joins log state
  const [joins, setJoins] = useState<InviteJoinRecord[]>([]);
  const [joinsTotal, setJoinsTotal] = useState(0);
  const [joinsPage, setJoinsPage] = useState(1);
  const [joinsTotalPages, setJoinsTotalPages] = useState(1);
  const [joinSourceFilter, setJoinSourceFilter] = useState<string>('ALL');
  const [joinSearch, setJoinSearch] = useState<string>('');

  // Modals state
  const [selectedInviteCode, setSelectedInviteCode] = useState<string | null>(null);
  const [inviteDetails, setInviteDetails] = useState<{
    invite: DiscordTrackedInvite;
    joins: InviteJoinRecord[];
    total_joins: number;
  } | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [userProfile, setUserProfile] = useState<UserInviteProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  const [copiedCode, setCopiedCode] = useState<string | null>(null);
  const [revokingCode, setRevokingCode] = useState<string | null>(null);

  // 1. Fetch overview stats, health, and leaderboard
  const fetchOverview = useCallback(async () => {
    try {
      const [statsData, healthData, lbData] = await Promise.all([
        invitesApi.getStats(timeframe),
        invitesApi.getHealth(),
        invitesApi.getLeaderboard(10),
      ]);
      setStats(statsData);
      setHealth(healthData);
      setLeaderboard(lbData.leaderboard || []);
    } catch (err: any) {
      toast.error('Failed to load invite statistics: ' + (err.message || 'Unknown error'));
    }
  }, [timeframe]);

  // 2. Fetch invites table
  const fetchInvites = useCallback(async () => {
    try {
      const res = await invitesApi.getInvites({
        status: inviteStatusFilter !== 'ALL' ? inviteStatusFilter : undefined,
        search: inviteSearch.trim() || undefined,
        page: invitesPage,
        page_size: 20,
      });
      setInvites(res.items || []);
      setInvitesTotal(res.total || 0);
      setInvitesTotalPages(res.total_pages || 1);
    } catch (err: any) {
      toast.error('Failed to load invites list: ' + (err.message || 'Unknown error'));
    }
  }, [inviteStatusFilter, inviteSearch, invitesPage]);

  // 3. Fetch joins log
  const fetchJoins = useCallback(async () => {
    try {
      const res = await invitesApi.getJoinsHistory({
        source_type: joinSourceFilter !== 'ALL' ? joinSourceFilter : undefined,
        search: joinSearch.trim() || undefined,
        page: joinsPage,
        page_size: 20,
      });
      setJoins(res.items || []);
      setJoinsTotal(res.total || 0);
      setJoinsTotalPages(res.total_pages || 1);
    } catch (err: any) {
      toast.error('Failed to load joins log: ' + (err.message || 'Unknown error'));
    }
  }, [joinSourceFilter, joinSearch, joinsPage]);

  // Fetch Activity Log settings & Discord channels
  const fetchActivitySettings = useCallback(async () => {
    try {
      setLoadingActivity(true);
      const [settingsData, channelsData] = await Promise.all([
        invitesApi.getActivitySettings(),
        invitesApi.getActivityChannels(),
      ]);
      setActivitySettings(settingsData);
      setActivityChannels(channelsData || []);
      setActivityForm({
        enabled: settingsData.enabled,
        channel_id: settingsData.channel_id || '',
        title_template: settingsData.title_template || '🎉 NEW MEMBER INVITED',
        description_template: settingsData.description_template || '{inviter_mention} invited {member_mention}',
        color_hex: settingsData.color_hex || '#5865F2',
        log_unknown: settingsData.log_unknown,
        log_vanity: settingsData.log_vanity,
        log_created: settingsData.log_created,
        log_revoked: settingsData.log_revoked,
      });
    } catch (err: any) {
      toast.error('Failed to load invite activity settings: ' + (err.message || 'Unknown error'));
    } finally {
      setLoadingActivity(false);
    }
  }, []);

  const handleSaveActivitySettings = async () => {
    try {
      setSavingActivity(true);
      const updated = await invitesApi.updateActivitySettings({
        enabled: activityForm.enabled,
        channel_id: activityForm.channel_id ? activityForm.channel_id : null,
        title_template: activityForm.title_template,
        description_template: activityForm.description_template,
        color_hex: activityForm.color_hex,
        log_unknown: activityForm.log_unknown,
        log_vanity: activityForm.log_vanity,
        log_created: activityForm.log_created,
        log_revoked: activityForm.log_revoked,
      });
      setActivitySettings(updated);
      toast.success('Invite activity channel settings saved successfully!');
      fetchOverview();
    } catch (err: any) {
      toast.error('Failed to save activity settings: ' + (err.message || 'Unknown error'));
    } finally {
      setSavingActivity(false);
    }
  };

  const handleResetActivityTemplate = async () => {
    try {
      setSavingActivity(true);
      const res = await invitesApi.resetActivitySettings();
      setActivitySettings(res);
      setActivityForm((prev) => ({
        ...prev,
        title_template: res.title_template,
        description_template: res.description_template,
        color_hex: res.color_hex,
      }));
      toast.success('Template reset to default values.');
    } catch (err: any) {
      toast.error('Failed to reset template: ' + (err.message || 'Unknown error'));
    } finally {
      setSavingActivity(false);
    }
  };

  const handleTestActivityLog = async () => {
    try {
      setTestingActivity(true);
      const res = await invitesApi.testActivityLog();
      toast.success(`Test invite notification sent to #${res.channel_name}!`);
    } catch (err: any) {
      toast.error('Test notification failed: ' + (err.message || 'Unknown error'));
    } finally {
      setTestingActivity(false);
    }
  };

  // Initial load
  useEffect(() => {
    setLoading(true);
    Promise.all([fetchOverview(), fetchInvites(), fetchJoins(), fetchActivitySettings()]).finally(() => {
      setLoading(false);
    });
  }, [fetchOverview, fetchInvites, fetchJoins, fetchActivitySettings]);

  // Re-fetch overview when timeframe changes
  useEffect(() => {
    fetchOverview();
  }, [timeframe, fetchOverview]);

  // Re-fetch invites when filters or page change
  useEffect(() => {
    fetchInvites();
  }, [fetchInvites]);

  // Re-fetch joins when filters or page change
  useEffect(() => {
    fetchJoins();
  }, [fetchJoins]);

  // Re-fetch activity settings when tab switches to activity
  useEffect(() => {
    if (activeTab === 'activity') {
      fetchActivitySettings();
    }
  }, [activeTab, fetchActivitySettings]);

  const selectedChannel = activityChannels.find((c) => c.id === activityForm.channel_id);

  const previewVars: Record<string, string> = {
    inviter: 'Rex12400',
    inviter_mention: '@Rex12400',
    inviter_id: '123456789012345678',
    member: 'Rahul',
    member_mention: '@Rahul',
    member_id: '987654321098765432',
    invite_code: 'xFP2SD3UVF',
    invite_channel: selectedChannel ? `#${selectedChannel.name}` : '# 🦋┃INVITES',
    total_invites: '12',
    rank: '#1',
    joined_at: 'Today at 12:35 PM',
    server_name: 'PB HERO Server',
  };

  const renderPreview = (text: string) => {
    let result = text || '';
    for (const [k, v] of Object.entries(previewVars)) {
      result = result.split(`{${k}}`).join(v);
    }
    return result;
  };

  // Copy to clipboard helper
  const handleCopy = (code: string) => {
    const url = `https://discord.gg/${code}`;
    navigator.clipboard.writeText(url);
    setCopiedCode(code);
    toast.success(`Copied invite link: ${url}`);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  // Force manual sync
  const handleForceSync = async () => {
    setSyncing(true);
    try {
      const res = await invitesApi.syncInvites();
      toast.success(`Synced successfully: ${res.active_invites} active invites refreshed.`);
      await Promise.all([fetchOverview(), fetchInvites(), fetchJoins()]);
    } catch (err: any) {
      toast.error('Manual sync failed: ' + (err.message || 'Unknown error'));
    } finally {
      setSyncing(false);
    }
  };

  // Open invite details modal
  const handleOpenInviteDetails = async (code: string) => {
    setSelectedInviteCode(code);
    setDetailsLoading(true);
    try {
      const data = await invitesApi.getInviteDetails(code);
      setInviteDetails(data);
    } catch (err: any) {
      toast.error('Failed to load invite details: ' + (err.message || 'Unknown error'));
      setSelectedInviteCode(null);
    } finally {
      setDetailsLoading(false);
    }
  };

  // Open user profile modal
  const handleOpenUserProfile = async (userId: string) => {
    setSelectedUserId(userId);
    setProfileLoading(true);
    try {
      const data = await invitesApi.getUserProfile(userId);
      setUserProfile(data);
    } catch (err: any) {
      toast.error('Failed to load user profile: ' + (err.message || 'Unknown error'));
      setSelectedUserId(null);
    } finally {
      setProfileLoading(false);
    }
  };

  // Revoke invite handler
  const handleRevokeInvite = async (code: string) => {
    if (!window.confirm(`Are you sure you want to revoke invite ${code}? Historical joins will be preserved.`)) {
      return;
    }
    setRevokingCode(code);
    try {
      await invitesApi.revokeInvite(code);
      toast.success(`Invite ${code} has been revoked.`);
      await Promise.all([fetchInvites(), fetchOverview()]);
      if (selectedInviteCode === code) {
        setSelectedInviteCode(null);
      }
    } catch (err: any) {
      toast.error('Failed to revoke invite: ' + (err.message || 'Unknown error'));
    } finally {
      setRevokingCode(null);
    }
  };

  // Helper badge for invite status
  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'ACTIVE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            ACTIVE
          </span>
        );
      case 'REVOKED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            REVOKED
          </span>
        );
      case 'EXPIRED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            EXPIRED
          </span>
        );
      case 'MAX_USES_REACHED':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            MAX USES
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-gray-700 text-gray-300">
            {status}
          </span>
        );
    }
  };

  // Helper badge for source type
  const renderSourceBadge = (source: string) => {
    switch (source) {
      case 'NORMAL_INVITE':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Link2 className="w-3 h-3" />
            INVITE
          </span>
        );
      case 'VANITY_URL':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-sky-500/10 text-sky-400 border border-sky-500/20">
            <ExternalLink className="w-3 h-3" />
            VANITY
          </span>
        );
      case 'UNKNOWN':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-gray-800 text-gray-400 border border-gray-700">
            <AlertCircle className="w-3 h-3" />
            UNKNOWN
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-gray-800 text-gray-300">
            {source}
          </span>
        );
    }
  };

  const renderPermissionBadge = (status?: string) => {
    const s = (status || 'UNAVAILABLE').toUpperCase();
    switch (s) {
      case 'READY':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-3 h-3" />
            Ready
          </span>
        );
      case 'MISSING_PERMISSION':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <AlertCircle className="w-3 h-3" />
            Missing permission
          </span>
        );
      case 'UNAVAILABLE':
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
            <X className="w-3 h-3" />
            Unavailable
          </span>
        );
    }
  };

  if (loading && !stats) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="h-10 w-72 bg-gray-800 animate-pulse rounded-xl" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-28 bg-[#151921] border border-gray-800 rounded-2xl animate-pulse" />
          ))}
        </div>
        <LoadingSkeleton rows={8} />
      </div>
    );
  }

  const isDegraded = health?.status === 'DEGRADED';
  const isError = health?.status === 'ERROR';

  return (
    <div className="space-y-8 animate-fade-in max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-[#5865F2]/10 border border-[#5865F2]/20 rounded-2xl text-[#5865F2]">
              <Link2 className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                <span>Discord Invite Tracking</span>
                {health && (
                  <span
                    className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${
                      health.status === 'HEALTHY'
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                        : isDegraded
                        ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                        : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                    }`}
                  >
                    <span
                      className={`w-2 h-2 rounded-full ${
                        health.status === 'HEALTHY'
                          ? 'bg-emerald-400 animate-pulse'
                          : isDegraded
                          ? 'bg-amber-400'
                          : 'bg-rose-400'
                      }`}
                    />
                    {health.status}
                  </span>
                )}
              </h1>
              <p className="text-xs text-gray-400 mt-1">
                Reliable member join attribution, referral leaderboard, and real-time invite analytics.
              </p>
            </div>
          </div>
        </div>

        {/* Header Actions */}
        <div className="flex items-center gap-3 self-start md:self-auto">
          {/* Timeframe Selector */}
          <div className="flex items-center bg-[#151921] border border-gray-800 rounded-xl p-1 text-xs font-semibold">
            {(['today', '7d', '30d', 'all'] as const).map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`px-3 py-1.5 rounded-lg transition-all ${
                  timeframe === tf
                    ? 'bg-[#5865F2] text-white shadow'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800/40'
                }`}
              >
                {tf === 'today' ? 'Today' : tf === '7d' ? '7 Days' : tf === '30d' ? '30 Days' : 'All Time'}
              </button>
            ))}
          </div>

          <button
            onClick={handleForceSync}
            disabled={syncing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-xs font-bold rounded-xl transition-all border border-gray-700 disabled:opacity-50"
            title="Refresh guild invites from Discord"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin text-[#5865F2]' : ''}`} />
            <span>{syncing ? 'Syncing...' : 'Sync Invites'}</span>
          </button>
        </div>
      </div>

      {/* Permission Warning Banner if Degraded */}
      {(isDegraded || isError) && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 text-amber-200 text-xs flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1">
            <span className="font-bold text-sm block text-amber-300">
              Invite Tracking Status: {health?.status}
            </span>
            <p className="text-amber-200/90 leading-relaxed">
              {health?.sync_error || health?.permissions?.details || 'Bot cannot read guild invites.'}
            </p>
            <p className="text-amber-300/70 text-[11px]">
              Tip: Grant the bot the <strong className="underline">Manage Server</strong> permission or check Server Members gateway intent to enable automatic invite attribution.
            </p>
          </div>
        </div>
      )}

      {/* Overview Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* TOTAL JOINS */}
        <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
          <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
            <span>Total Joins</span>
            <Users className="w-4 h-4 text-[#5865F2]" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-white tracking-tight">
              {stats?.total_joins ?? 0}
            </span>
            <span className="text-xs text-emerald-400 font-semibold">
              {stats?.normal_joins ?? 0} attributed
            </span>
          </div>
          <span className="text-[11px] text-gray-500 mt-1 block">
            {timeframe === 'all' ? 'All-time joined members' : `Joined in selected period`}
          </span>
        </div>

        {/* TOTAL INVITES */}
        <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
          <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
            <span>Invite Links</span>
            <Link2 className="w-4 h-4 text-sky-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-white tracking-tight">
              {stats?.total_invites ?? 0}
            </span>
            <span className="text-xs text-gray-400">total links</span>
          </div>
          <span className="text-[11px] text-gray-500 mt-1 block">
            Generated by server members
          </span>
        </div>

        {/* ACTIVE INVITES */}
        <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
          <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
            <span>Active Invites</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-emerald-400 tracking-tight">
              {stats?.active_invites ?? 0}
            </span>
            <span className="text-xs text-gray-400">valid links</span>
          </div>
          <span className="text-[11px] text-gray-500 mt-1 block">
            Usable right now in Discord
          </span>
        </div>

        {/* TOP INVITER */}
        <div
          onClick={() => {
            const top = leaderboard[0];
            if (top) handleOpenUserProfile(top.user_id);
          }}
          className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-indigo-500/50 cursor-pointer transition-all"
        >
          <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
            <span>Top Inviter</span>
            <UserCheck className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-3 truncate">
            <span className="text-xl font-black text-white tracking-tight block truncate group-hover:text-[#858eff] transition-colors">
              {stats?.top_inviter?.name && stats.top_inviter.name !== 'None'
                ? stats.top_inviter.name
                : 'None yet'}
            </span>
            <span className="text-xs text-amber-400 font-semibold block mt-0.5">
              {stats?.top_inviter?.count ?? 0} members referred
            </span>
          </div>
          <span className="text-[10px] text-gray-500 mt-1 block">
            Click to view member profile
          </span>
        </div>

        {/* UNKNOWN JOINS */}
        <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
          <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
            <span>Unknown Joins</span>
            <AlertCircle className="w-4 h-4 text-gray-400" />
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-black text-gray-300 tracking-tight">
              {stats?.unknown_joins ?? 0}
            </span>
            {stats?.vanity_joins ? (
              <span className="text-xs text-sky-400 font-semibold">
                +{stats.vanity_joins} vanity
              </span>
            ) : (
              <span className="text-xs text-gray-500">no invite match</span>
            )}
          </div>
          <span className="text-[11px] text-gray-500 mt-1 block">
            Widgets, integrations, or unknown
          </span>
        </div>
      </div>

      {/* Main Tabs Navigation */}
      <div className="border-b border-gray-800 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('invites')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'invites'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Link2 className="w-4 h-4" />
            <span>Tracked Invites & Leaderboard</span>
          </button>

          <button
            onClick={() => setActiveTab('joins')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'joins'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Users className="w-4 h-4" />
            <span>Join Attribution History</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-gray-800 text-[10px] text-gray-400">
              {joinsTotal}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('activity')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'activity'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Radio className="w-4 h-4" />
            <span>Invite Activity Channel & Logs</span>
            {activitySettings?.enabled && (
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
            )}
          </button>

          <button
            onClick={() => setActiveTab('diagnostics')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'diagnostics'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Activity className="w-4 h-4" />
            <span>Tracker Health & Permissions</span>
          </button>
        </div>
      </div>

      {/* TAB 1: TRACKED INVITES & LEADERBOARD */}
      {activeTab === 'invites' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 items-start">
          {/* Main Invites Table (2 Cols) */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filter Bar */}
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-4 flex flex-col sm:flex-row gap-3 items-center justify-between shadow-lg">
              <div className="relative w-full sm:w-72">
                <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
                <input
                  type="text"
                  placeholder="Search code, inviter, channel..."
                  value={inviteSearch}
                  onChange={(e) => {
                    setInviteSearch(e.target.value);
                    setInvitesPage(1);
                  }}
                  className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] transition-colors"
                />
              </div>

              <div className="flex items-center gap-2.5 w-full sm:w-auto">
                <select
                  value={inviteStatusFilter}
                  onChange={(e) => {
                    setInviteStatusFilter(e.target.value);
                    setInvitesPage(1);
                  }}
                  className="bg-[#0B0E14] border border-gray-800 rounded-xl px-3 py-2 text-xs text-white font-medium focus:outline-none focus:border-[#5865F2] transition-colors"
                >
                  <option value="ALL">All Statuses</option>
                  <option value="ACTIVE">Active</option>
                  <option value="REVOKED">Revoked</option>
                  <option value="EXPIRED">Expired</option>
                  <option value="MAX_USES_REACHED">Max Uses</option>
                </select>
              </div>
            </div>

            {/* Invites Table Card */}
            <div className="bg-[#151921] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-[#0e1219] border-b border-gray-800 text-gray-400 font-bold uppercase tracking-wider">
                    <tr>
                      <th className="py-3.5 px-4">Invite Code</th>
                      <th className="py-3.5 px-4">Inviter</th>
                      <th className="py-3.5 px-4">Channel</th>
                      <th className="py-3.5 px-4 text-center">Uses</th>
                      <th className="py-3.5 px-4 text-center">Tracked Joins</th>
                      <th className="py-3.5 px-4">Status</th>
                      <th className="py-3.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 font-medium text-gray-300">
                    {invites.length === 0 ? (
                      <tr>
                        <td colSpan={7} className="py-12 text-center text-gray-500 text-xs">
                          No invite records found matching current criteria.
                        </td>
                      </tr>
                    ) : (
                      invites.map((inv) => (
                        <tr key={inv.invite_code} className="hover:bg-gray-800/30 transition-colors">
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-white bg-gray-900 px-2 py-1 rounded border border-gray-800">
                                {inv.invite_code}
                              </span>
                              <button
                                onClick={() => handleCopy(inv.invite_code)}
                                className="text-gray-500 hover:text-white transition-colors"
                                title="Copy link"
                              >
                                {copiedCode === inv.invite_code ? (
                                  <Check className="w-3.5 h-3.5 text-emerald-400" />
                                ) : (
                                  <Copy className="w-3.5 h-3.5" />
                                )}
                              </button>
                            </div>
                          </td>
                          <td className="py-3.5 px-4">
                            {inv.inviter_id ? (
                              <button
                                onClick={() => handleOpenUserProfile(inv.inviter_id!)}
                                className="text-[#858eff] hover:underline font-semibold flex items-center gap-1.5 truncate max-w-[140px]"
                              >
                                <User className="w-3 h-3 shrink-0" />
                                <span className="truncate">{inv.inviter_name || 'Member'}</span>
                              </button>
                            ) : (
                              <span className="text-gray-400 flex items-center gap-1.5 truncate max-w-[140px]">
                                {inv.inviter_name || 'Server'}
                              </span>
                            )}
                          </td>
                          <td className="py-3.5 px-4 text-gray-400 font-mono text-[11px]">
                            {inv.channel_name ? `#${inv.channel_name}` : 'Unknown'}
                          </td>
                          <td className="py-3.5 px-4 text-center font-bold text-gray-200">
                            {inv.uses}
                          </td>
                          <td className="py-3.5 px-4 text-center font-bold text-emerald-400">
                            {inv.tracked_joins}
                          </td>
                          <td className="py-3.5 px-4">
                            {renderStatusBadge(inv.status)}
                          </td>
                          <td className="py-3.5 px-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => handleOpenInviteDetails(inv.invite_code)}
                                className="px-2.5 py-1 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-[11px] font-semibold transition-colors"
                              >
                                Details
                              </button>
                              {inv.status === 'ACTIVE' && (
                                <button
                                  onClick={() => handleRevokeInvite(inv.invite_code)}
                                  disabled={revokingCode === inv.invite_code}
                                  className="p-1 text-gray-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
                                  title="Revoke invite link"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {invitesTotalPages > 1 && (
                <div className="p-3.5 border-t border-gray-800 bg-[#0e1219] flex items-center justify-between text-xs text-gray-400">
                  <span>
                    Showing {invites.length} of {invitesTotal} invites
                  </span>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setInvitesPage((p) => Math.max(1, p - 1))}
                      disabled={invitesPage <= 1}
                      className="p-1.5 rounded-lg border border-gray-800 hover:bg-gray-800 disabled:opacity-40 transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <span className="font-semibold text-white">
                      {invitesPage} / {invitesTotalPages}
                    </span>
                    <button
                      onClick={() => setInvitesPage((p) => Math.min(invitesTotalPages, p + 1))}
                      disabled={invitesPage >= invitesTotalPages}
                      className="p-1.5 rounded-lg border border-gray-800 hover:bg-gray-800 disabled:opacity-40 transition-colors"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Right Column: Invite Leaderboard */}
          <div className="space-y-4">
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-5 shadow-xl space-y-4">
              <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                <h2 className="text-sm font-bold text-white flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-amber-400" />
                  <span>Invite Leaderboard</span>
                </h2>
                <span className="text-[10px] text-gray-500 uppercase font-semibold">
                  Top Inviters
                </span>
              </div>

              {leaderboard.length === 0 ? (
                <div className="py-8 text-center text-gray-500 text-xs">
                  No attributed member joins yet.
                </div>
              ) : (
                <div className="space-y-2.5">
                  {leaderboard.map((item) => (
                    <div
                      key={item.user_id}
                      onClick={() => handleOpenUserProfile(item.user_id)}
                      className="p-3 bg-[#0B0E14] hover:bg-gray-800/40 border border-gray-800/80 rounded-xl cursor-pointer transition-all group"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5 truncate">
                          <span
                            className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                              item.rank === 1
                                ? 'bg-amber-400/20 text-amber-400 border border-amber-400/30'
                                : item.rank === 2
                                ? 'bg-slate-300/20 text-slate-300 border border-slate-300/30'
                                : item.rank === 3
                                ? 'bg-amber-700/20 text-amber-600 border border-amber-700/30'
                                : 'bg-gray-800 text-gray-400'
                            }`}
                          >
                            {item.rank}
                          </span>
                          <span className="font-semibold text-xs text-white truncate group-hover:text-[#858eff] transition-colors">
                            {item.username}
                          </span>
                        </div>
                        <div className="text-right shrink-0">
                          <span className="text-xs font-black text-emerald-400">
                            {item.joins} joins
                          </span>
                        </div>
                      </div>

                      {/* Progress bar */}
                      <div className="mt-2 flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-[#5865F2] to-emerald-400 rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(100, Math.max(5, item.percentage))}%` }}
                          />
                        </div>
                        <span className="text-[10px] text-gray-500 font-mono">
                          {item.percentage}%
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: JOIN ATTRIBUTION LOG */}
      {activeTab === 'joins' && (
        <div className="space-y-4">
          {/* Joins Filter Bar */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-4 flex flex-col sm:flex-row gap-3 items-center justify-between shadow-lg">
            <div className="relative w-full sm:w-72">
              <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                placeholder="Search member, inviter, code..."
                value={joinSearch}
                onChange={(e) => {
                  setJoinSearch(e.target.value);
                  setJoinsPage(1);
                }}
                className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl pl-9 pr-3.5 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] transition-colors"
              />
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <select
                value={joinSourceFilter}
                onChange={(e) => {
                  setJoinSourceFilter(e.target.value);
                  setJoinsPage(1);
                }}
                className="bg-[#0B0E14] border border-gray-800 rounded-xl px-3 py-2 text-xs text-white font-medium focus:outline-none focus:border-[#5865F2] transition-colors"
              >
                <option value="ALL">All Source Types</option>
                <option value="NORMAL_INVITE">Normal Invite</option>
                <option value="VANITY_URL">Vanity URL</option>
                <option value="UNKNOWN">Unknown</option>
              </select>
            </div>
          </div>

          {/* Joins Table */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#0e1219] border-b border-gray-800 text-gray-400 font-bold uppercase tracking-wider">
                  <tr>
                    <th className="py-3.5 px-4">Member</th>
                    <th className="py-3.5 px-4">Source Type</th>
                    <th className="py-3.5 px-4">Invite Code</th>
                    <th className="py-3.5 px-4">Attributed Inviter</th>
                    <th className="py-3.5 px-4">Destination Channel</th>
                    <th className="py-3.5 px-4">Joined At</th>
                    <th className="py-3.5 px-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800/60 font-medium text-gray-300">
                  {joins.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-12 text-center text-gray-500 text-xs">
                        No member joins recorded yet.
                      </td>
                    </tr>
                  ) : (
                    joins.map((j) => (
                      <tr key={j.id} className="hover:bg-gray-800/30 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{j.member_name || `Member ${j.member_id}`}</span>
                            <span className="text-[10px] text-gray-500 font-mono">({j.member_id})</span>
                          </div>
                        </td>
                        <td className="py-3.5 px-4">
                          {renderSourceBadge(j.source_type)}
                        </td>
                        <td className="py-3.5 px-4">
                          {j.invite_code ? (
                            <button
                              onClick={() => handleOpenInviteDetails(j.invite_code!)}
                              className="font-mono text-xs text-[#858eff] hover:underline"
                            >
                              {j.invite_code}
                            </button>
                          ) : (
                            <span className="text-gray-500">—</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4">
                          {j.inviter_id ? (
                            <button
                              onClick={() => handleOpenUserProfile(j.inviter_id!)}
                              className="text-[#858eff] hover:underline font-semibold"
                            >
                              {j.inviter_name || j.inviter_id}
                            </button>
                          ) : (
                            <span className="text-gray-400">{j.inviter_name || '—'}</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 text-gray-400 font-mono text-[11px]">
                          {j.channel_name ? `#${j.channel_name}` : '—'}
                        </td>
                        <td className="py-3.5 px-4 text-gray-400">
                          {j.joined_at ? new Date(j.joined_at).toLocaleString() : 'Unknown'}
                        </td>
                        <td className="py-3.5 px-4">
                          {j.is_still_member ? (
                            <span className="text-emerald-400 text-[11px] font-semibold">Active Member</span>
                          ) : (
                            <span className="text-gray-500 text-[11px]">Left Server</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {joinsTotalPages > 1 && (
              <div className="p-3.5 border-t border-gray-800 bg-[#0e1219] flex items-center justify-between text-xs text-gray-400">
                <span>
                  Showing {joins.length} of {joinsTotal} joins
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setJoinsPage((p) => Math.max(1, p - 1))}
                    disabled={joinsPage <= 1}
                    className="p-1.5 rounded-lg border border-gray-800 hover:bg-gray-800 disabled:opacity-40 transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="font-semibold text-white">
                    {joinsPage} / {joinsTotalPages}
                  </span>
                  <button
                    onClick={() => setJoinsPage((p) => Math.min(joinsTotalPages, p + 1))}
                    disabled={joinsPage >= joinsTotalPages}
                    className="p-1.5 rounded-lg border border-gray-800 hover:bg-gray-800 disabled:opacity-40 transition-colors"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: INVITE ACTIVITY LOG & CHANNEL CONFIGURATION */}
      {activeTab === 'activity' && (
        <div className="space-y-6">
          {/* Top Info & Action Card */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-[#5865F2]/10 border border-[#5865F2]/20 rounded-xl text-[#5865F2]">
                  <Radio className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base font-extrabold text-white flex items-center gap-2">
                    <span>Invite Activity Channel & Notification System</span>
                    {activitySettings?.enabled ? (
                      selectedChannel?.is_ready ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" />
                          ACTIVE & READY
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <AlertCircle className="w-3 h-3" />
                          DEGRADED
                        </span>
                      )
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-gray-800 text-gray-400 border border-gray-700">
                        DISABLED
                      </span>
                    )}
                  </h2>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Select where invite tracking activity will be posted in Discord, configure templates, and test live embeds.
                  </p>
                </div>
              </div>
            </div>

            {/* Quick Action Buttons */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleTestActivityLog}
                disabled={testingActivity || !activityForm.channel_id}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-xs font-bold rounded-xl border border-gray-700 transition-all disabled:opacity-40 disabled:cursor-not-allowed shadow-md"
                title={!activityForm.channel_id ? 'Select a channel first to send test notification' : 'Send test embed to Discord'}
              >
                <Send className={`w-3.5 h-3.5 ${testingActivity ? 'animate-bounce' : ''}`} />
                <span>{testingActivity ? 'Sending Test...' : 'Test Invite Log'}</span>
              </button>

              <button
                type="button"
                onClick={handleSaveActivitySettings}
                disabled={savingActivity}
                className="inline-flex items-center gap-2 px-5 py-2 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-[#5865F2]/20 disabled:opacity-50"
              >
                <Check className="w-4 h-4" />
                <span>{savingActivity ? 'Saving...' : 'Save Configuration'}</span>
              </button>
            </div>
          </div>

          {loadingActivity ? (
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-8">
              <LoadingSkeleton rows={6} />
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              {/* Left Column: Settings Form (7 cols) */}
              <div className="lg:col-span-7 space-y-6">
                {/* 1. Channel Selector Card */}
                <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-5">
                  <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                    <div className="flex items-center gap-2">
                      <Hash className="w-4 h-4 text-[#5865F2]" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                        Destination Discord Channel
                      </h3>
                    </div>

                    {/* Enable Toggle Switch */}
                    <label className="flex items-center gap-2.5 cursor-pointer">
                      <span className="text-xs font-semibold text-gray-300">
                        Enable Invite Activity Logs
                      </span>
                      <div className="relative">
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={activityForm.enabled}
                          onChange={(e) =>
                            setActivityForm((prev) => ({ ...prev, enabled: e.target.checked }))
                          }
                        />
                        <div
                          className={`w-11 h-6 rounded-full transition-colors ${
                            activityForm.enabled ? 'bg-[#5865F2]' : 'bg-gray-700'
                          }`}
                        >
                          <div
                            className={`w-4 h-4 rounded-full bg-white transition-transform transform mt-1 ml-1 ${
                              activityForm.enabled ? 'translate-x-5' : 'translate-x-0'
                            }`}
                          />
                        </div>
                      </div>
                    </label>
                  </div>

                  {/* Channel Dropdown */}
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-gray-300 block">
                      Target Text Channel
                    </label>
                    <select
                      value={activityForm.channel_id}
                      onChange={(e) =>
                        setActivityForm((prev) => ({ ...prev, channel_id: e.target.value }))
                      }
                      className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white font-medium focus:outline-none focus:border-[#5865F2] transition-colors"
                    >
                      <option value="">No channel selected (Activity logs disabled in Discord)</option>
                      {activityChannels.map((c) => (
                        <option
                          key={c.id}
                          value={c.id}
                          disabled={!c.can_view || !c.can_send || !c.can_embed}
                        >
                          #{c.name} {c.permission_status === 'READY' ? '— ✅ Ready' : c.permission_status === 'MISSING_PERMISSION' ? '— ⚠️ Missing permission' : '— ❌ Unavailable'}
                        </option>
                      ))}
                    </select>
                    <p className="text-[11px] text-gray-500">
                      Select where invite tracking activity will be posted in Discord. If no channel is selected, invite activity remains stored in the dashboard/database, but nothing is posted to Discord.
                    </p>
                  </div>

                  {/* Selected Channel Permission Diagnostics */}
                  {selectedChannel && (
                    <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-3 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-white flex items-center gap-1.5">
                          <Hash className="w-3.5 h-3.5 text-gray-400" />
                          <span>#{selectedChannel.name}</span>
                        </span>
                        {renderPermissionBadge(selectedChannel.permission_status)}
                      </div>

                      <div className="grid grid-cols-3 gap-2 text-[11px] pt-1 border-t border-gray-800/80">
                        <div className="flex items-center gap-1.5">
                          {selectedChannel.can_view ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <X className="w-3.5 h-3.5 text-rose-400" />
                          )}
                          <span className={selectedChannel.can_view ? 'text-gray-300' : 'text-rose-400'}>
                            View Channel
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {selectedChannel.can_send ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <X className="w-3.5 h-3.5 text-rose-400" />
                          )}
                          <span className={selectedChannel.can_send ? 'text-gray-300' : 'text-rose-400'}>
                            Send Messages
                          </span>
                        </div>

                        <div className="flex items-center gap-1.5">
                          {selectedChannel.can_embed ? (
                            <Check className="w-3.5 h-3.5 text-emerald-400" />
                          ) : (
                            <X className="w-3.5 h-3.5 text-rose-400" />
                          )}
                          <span className={selectedChannel.can_embed ? 'text-gray-300' : 'text-rose-400'}>
                            Embed Links
                          </span>
                        </div>
                      </div>

                      {!selectedChannel.is_ready && (
                        <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-[11px] flex items-start gap-2">
                          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
                          <div>
                            <span className="font-bold">DEGRADED: </span>
                            {selectedChannel.reason || 'Bot cannot send messages to this channel.'}
                            <div className="text-[10px] text-rose-400/80 mt-0.5">
                              Please verify bot role permissions in Discord: View Channel, Send Messages, and Embed Links.
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* 2. Event Filters Card */}
                <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
                    <Sliders className="w-4 h-4 text-[#5865F2]" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                      Event Notification Filters
                    </h3>
                  </div>

                  <p className="text-xs text-gray-400">
                    Choose which Discord invite activity events trigger public log messages:
                  </p>

                  <div className="space-y-3">
                    {/* Successful Attributed Join */}
                    <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800/80 opacity-90">
                      <div className="flex items-center gap-3">
                        <span className="text-base">🎉</span>
                        <div>
                          <span className="text-xs font-semibold text-white block">
                            Successful Attributed Join
                          </span>
                          <span className="text-[11px] text-gray-400">
                            Posts full inviter attribution, referral count, and current rank.
                          </span>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={true}
                        disabled
                        className="rounded border-gray-700 text-[#5865F2] focus:ring-0 cursor-not-allowed"
                      />
                    </div>

                    {/* Unknown Join */}
                    <label className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800/80 hover:border-gray-700 cursor-pointer transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="text-base">⚠️</span>
                        <div>
                          <span className="text-xs font-semibold text-white block">
                            Unknown Join (No false attribution)
                          </span>
                          <span className="text-[11px] text-gray-400">
                            Posts a clean generic join log without assigning false credit or incrementing counters.
                          </span>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={activityForm.log_unknown}
                        onChange={(e) =>
                          setActivityForm((prev) => ({ ...prev, log_unknown: e.target.checked }))
                        }
                        className="rounded border-gray-700 text-[#5865F2] focus:ring-0 cursor-pointer"
                      />
                    </label>

                    {/* Vanity URL Join */}
                    <label className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800/80 hover:border-gray-700 cursor-pointer transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="text-base">✨</span>
                        <div>
                          <span className="text-xs font-semibold text-white block">
                            Vanity URL Join
                          </span>
                          <span className="text-[11px] text-gray-400">
                            Posts a vanity attribution notice without adding joins to personal inviter leaderboards.
                          </span>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={activityForm.log_vanity}
                        onChange={(e) =>
                          setActivityForm((prev) => ({ ...prev, log_vanity: e.target.checked }))
                        }
                        className="rounded border-gray-700 text-[#5865F2] focus:ring-0 cursor-pointer"
                      />
                    </label>

                    {/* Invite Created */}
                    <label className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800/80 hover:border-gray-700 cursor-pointer transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="text-base">🔗</span>
                        <div>
                          <span className="text-xs font-semibold text-white block">
                            Invite Created Notice (Optional)
                          </span>
                          <span className="text-[11px] text-gray-400">
                            Logs whenever a member creates a new invite code for this server.
                          </span>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={activityForm.log_created}
                        onChange={(e) =>
                          setActivityForm((prev) => ({ ...prev, log_created: e.target.checked }))
                        }
                        className="rounded border-gray-700 text-[#5865F2] focus:ring-0 cursor-pointer"
                      />
                    </label>

                    {/* Invite Revoked */}
                    <label className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800/80 hover:border-gray-700 cursor-pointer transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="text-base">🗑️</span>
                        <div>
                          <span className="text-xs font-semibold text-white block">
                            Invite Revoked / Deleted Notice (Optional)
                          </span>
                          <span className="text-[11px] text-gray-400">
                            Logs whenever an invite code is deleted or revoked by staff.
                          </span>
                        </div>
                      </div>
                      <input
                        type="checkbox"
                        checked={activityForm.log_revoked}
                        onChange={(e) =>
                          setActivityForm((prev) => ({ ...prev, log_revoked: e.target.checked }))
                        }
                        className="rounded border-gray-700 text-[#5865F2] focus:ring-0 cursor-pointer"
                      />
                    </label>
                  </div>
                </div>

                {/* 3. Embed Template Editor */}
                <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                    <div className="flex items-center gap-2">
                      <Palette className="w-4 h-4 text-[#5865F2]" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                        Invite Activity Message Template
                      </h3>
                    </div>

                    <button
                      type="button"
                      onClick={handleResetActivityTemplate}
                      disabled={savingActivity}
                      className="inline-flex items-center gap-1.5 px-3 py-1 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg text-xs font-medium border border-gray-700 transition-colors"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>Reset to Default</span>
                    </button>
                  </div>

                  {/* Title & Color */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="sm:col-span-2 space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">
                        Embed Title Template
                      </label>
                      <input
                        type="text"
                        value={activityForm.title_template}
                        onChange={(e) =>
                          setActivityForm((prev) => ({ ...prev, title_template: e.target.value }))
                        }
                        className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2] transition-colors"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">
                        Accent Color Hex
                      </label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={activityForm.color_hex}
                          onChange={(e) =>
                            setActivityForm((prev) => ({ ...prev, color_hex: e.target.value }))
                          }
                          className="w-8 h-8 rounded-lg border border-gray-800 bg-transparent cursor-pointer"
                        />
                        <input
                          type="text"
                          value={activityForm.color_hex}
                          onChange={(e) =>
                            setActivityForm((prev) => ({ ...prev, color_hex: e.target.value }))
                          }
                          className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3 py-2 text-xs text-white font-mono uppercase focus:outline-none focus:border-[#5865F2] transition-colors"
                        />
                      </div>
                    </div>
                  </div>

                  {/* Description Template */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-300">
                      Description Template
                    </label>
                    <textarea
                      rows={2}
                      value={activityForm.description_template}
                      onChange={(e) =>
                        setActivityForm((prev) => ({ ...prev, description_template: e.target.value }))
                      }
                      className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2] transition-colors"
                    />
                  </div>

                  {/* Available Variables */}
                  <div className="space-y-2 pt-2 border-t border-gray-800/80">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-gray-400 block">
                      Available Variables (Click to copy)
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {[
                        '{inviter}',
                        '{inviter_mention}',
                        '{inviter_id}',
                        '{member}',
                        '{member_mention}',
                        '{member_id}',
                        '{invite_code}',
                        '{invite_channel}',
                        '{total_invites}',
                        '{rank}',
                        '{joined_at}',
                        '{server_name}',
                      ].map((v) => (
                        <button
                          key={v}
                          type="button"
                          onClick={() => {
                            navigator.clipboard.writeText(v);
                            toast.success(`Copied ${v} to clipboard`);
                          }}
                          className="px-2 py-1 rounded bg-[#0B0E14] hover:bg-gray-800 border border-gray-800 text-[11px] font-mono text-[#858eff] transition-colors"
                          title="Click to copy variable"
                        >
                          {v}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Live Discord Preview & Diagnostics (5 cols) */}
              <div className="lg:col-span-5 space-y-6">
                {/* Live Discord Embed Preview */}
                <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-gray-800 pb-3">
                    <div className="flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-amber-400" />
                      <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                        Discord Invite Log Preview
                      </h3>
                    </div>
                    <span className="text-[10px] text-gray-500 font-mono">Live Simulation</span>
                  </div>

                  {/* Discord Chat Container */}
                  <div className="bg-[#313338] rounded-xl p-4 text-xs font-sans text-gray-200 shadow-inner">
                    {/* Message Header */}
                    <div className="flex items-start gap-3 mb-2.5">
                      <div className="w-10 h-10 rounded-full bg-[#5865F2] flex items-center justify-center font-black text-white shrink-0 shadow-md">
                        PB
                      </div>
                      <div>
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-white text-sm">PB HERO</span>
                          <span className="bg-[#5865F2] text-white text-[9px] font-bold px-1 py-0.5 rounded leading-none">
                            BOT
                          </span>
                          <span className="text-[11px] text-gray-400 ml-1">Today at 12:35 PM</span>
                        </div>
                      </div>
                    </div>

                    {/* Simulated Discord Embed */}
                    <div
                      className="bg-[#2b2d31] rounded-r-lg p-3.5 space-y-3 shadow-md"
                      style={{ borderLeft: `4px solid ${activityForm.color_hex || '#5865F2'}` }}
                    >
                      {/* Embed Title */}
                      <div className="font-bold text-white text-sm">
                        {renderPreview(activityForm.title_template)}
                      </div>

                      {/* Embed Description */}
                      <div className="text-gray-300 text-xs">
                        {renderPreview(activityForm.description_template)}
                      </div>

                      {/* Embed Fields (2 cols) */}
                      <div className="grid grid-cols-2 gap-2.5 pt-1 text-xs">
                        <div>
                          <span className="font-bold text-gray-400 text-[10px] uppercase block">
                            👤 Inviter
                          </span>
                          <span className="text-white font-medium">Rex12400</span>
                        </div>
                        <div>
                          <span className="font-bold text-gray-400 text-[10px] uppercase block">
                            👥 New Member
                          </span>
                          <span className="text-white font-medium">Rahul</span>
                        </div>
                        <div>
                          <span className="font-bold text-gray-400 text-[10px] uppercase block">
                            🔗 Invite
                          </span>
                          <span className="font-mono text-indigo-400 font-semibold">xFP2SD3UVF</span>
                        </div>
                        <div>
                          <span className="font-bold text-gray-400 text-[10px] uppercase block">
                            📍 Invite Channel
                          </span>
                          <span className="text-gray-300 font-mono">
                            {selectedChannel ? `#${selectedChannel.name}` : '# 🦋┃INVITES'}
                          </span>
                        </div>
                        <div>
                          <span className="font-bold text-gray-400 text-[10px] uppercase block">
                            📊 Total Invites
                          </span>
                          <span className="text-emerald-400 font-bold">12</span>
                        </div>
                        <div>
                          <span className="font-bold text-gray-400 text-[10px] uppercase block">
                            🏆 Current Rank
                          </span>
                          <span className="text-amber-400 font-bold">#1</span>
                        </div>
                      </div>

                      {/* Embed Footer */}
                      <div className="border-t border-gray-700/60 pt-2 text-[10px] text-gray-400 flex items-center justify-between">
                        <span>PB HERO Discord Invite Tracker</span>
                        <span>Today at 12:35 PM</span>
                      </div>
                    </div>
                  </div>

                  <p className="text-[11px] text-gray-500 italic">
                    The live preview accurately reflects current template settings with sample attribution test data.
                  </p>
                </div>

                {/* Status Diagnostic Card */}
                <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-4">
                  <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
                    <ShieldCheck className="w-4 h-4 text-[#5865F2]" />
                    <h3 className="text-xs font-bold uppercase tracking-wider text-white">
                      Invite Activity Diagnostics
                    </h3>
                  </div>

                  <div className="space-y-3 text-xs">
                    <div className="flex items-center justify-between bg-[#0B0E14] p-3 rounded-xl border border-gray-800/80">
                      <span className="text-gray-400">Activity System Enabled:</span>
                      <span
                        className={`font-bold ${
                          activityForm.enabled ? 'text-emerald-400' : 'text-gray-500'
                        }`}
                      >
                        {activityForm.enabled ? 'YES' : 'NO'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between bg-[#0B0E14] p-3 rounded-xl border border-gray-800/80">
                      <span className="text-gray-400">Channel Selected:</span>
                      <span
                        className={`font-semibold ${
                          activityForm.channel_id ? 'text-white' : 'text-gray-500'
                        }`}
                      >
                        {selectedChannel ? `#${selectedChannel.name}` : 'None'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between bg-[#0B0E14] p-3 rounded-xl border border-gray-800/80">
                      <span className="text-gray-400">Bot Channel Permissions:</span>
                      <span
                        className={`font-bold ${
                          selectedChannel?.is_ready ? 'text-emerald-400' : 'text-amber-400'
                        }`}
                      >
                        {selectedChannel?.is_ready ? 'ALL GRANTED (Ready)' : 'INSUFFICIENT'}
                      </span>
                    </div>
                  </div>

                  <div className="p-3 bg-[#0B0E14] rounded-xl border border-gray-800/80 text-[11px] text-gray-400 space-y-1">
                    <span className="font-bold text-gray-300 block">Spam & Reconnect Protection:</span>
                    <p>
                      Each member join generates at most one activity message. Reconnects and restarts do not replay historical joins.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 4: DIAGNOSTICS & HEALTH */}
      {activeTab === 'diagnostics' && (
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
          <div className="border-b border-gray-800 pb-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-[#5865F2]" />
                <span>Invite Tracking Diagnostics & Gateway State</span>
              </h2>
              <p className="text-xs text-gray-400 mt-0.5">
                Real-time verification of Discord API permissions, intent synchronization, and in-memory caches.
              </p>
            </div>
            <button
              onClick={handleForceSync}
              disabled={syncing}
              className="inline-flex items-center gap-2 px-4 py-2 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-[#5865F2]/20 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
              <span>{syncing ? 'Refreshing...' : 'Re-verify & Sync'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Gateway & Permissions */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                Discord Gateway & Permissions
              </h3>
              <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Manage Server Permission</span>
                  <span
                    className={`font-bold ${
                      health?.permissions?.has_manage_guild ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {health?.permissions?.has_manage_guild ? 'GRANTED' : 'MISSING'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Read Guild Invites Capability</span>
                  <span
                    className={`font-bold ${
                      health?.permissions?.can_read_invites ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {health?.permissions?.can_read_invites ? 'VERIFIED' : 'UNAVAILABLE'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Server Members Gateway Intent</span>
                  <span
                    className={`font-bold ${
                      health?.permissions?.intents_ok ? 'text-emerald-400' : 'text-amber-400'
                    }`}
                  >
                    {health?.permissions?.intents_ok ? 'ENABLED' : 'DISABLED'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Tracking Engine State</span>
                  <span className="font-bold text-white uppercase">{health?.status}</span>
                </div>
              </div>
            </div>

            {/* Sync Telemetry */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                Cache & Sync Timestamps
              </h3>
              <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Last Guild Invite Sync</span>
                  <span className="font-mono text-gray-300">
                    {health?.last_sync ? new Date(health.last_sync).toLocaleString() : 'Never'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Last Member Join Attribution</span>
                  <span className="font-mono text-gray-300">
                    {health?.last_attribution
                      ? new Date(health.last_attribution).toLocaleString()
                      : 'None yet'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Cached Active Invites (RAM)</span>
                  <span className="font-bold text-sky-400">{health?.tracked_invites_cached ?? 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Historical Database Joins</span>
                  <span className="font-bold text-emerald-400">{health?.total_joins ?? 0}</span>
                </div>
              </div>
            </div>

            {/* Activity Channel Status */}
            <div className="space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">
                Invite Activity Channel
              </h3>
              <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-3 text-xs">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Configured Destination</span>
                  <span className="font-mono text-white font-semibold truncate max-w-[130px]">
                    {health?.activity_channel?.configured
                      ? `#${health.activity_channel.channel_name}`
                      : 'None'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">View Channel</span>
                  <span
                    className={`font-bold ${
                      health?.activity_channel?.can_view ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {health?.activity_channel?.can_view ? 'GRANTED' : 'MISSING'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Send Messages</span>
                  <span
                    className={`font-bold ${
                      health?.activity_channel?.can_send ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {health?.activity_channel?.can_send ? 'GRANTED' : 'MISSING'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Embed Links</span>
                  <span
                    className={`font-bold ${
                      health?.activity_channel?.can_embed ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {health?.activity_channel?.can_embed ? 'GRANTED' : 'MISSING'}
                  </span>
                </div>
                <div className="flex items-center justify-between border-t border-gray-800/80 pt-2">
                  <span className="text-gray-400">Delivery Status</span>
                  <span
                    className={`font-bold ${
                      !health?.activity_channel?.configured
                        ? 'text-gray-400'
                        : health?.activity_channel?.is_ready
                        ? 'text-emerald-400'
                        : 'text-amber-400'
                    }`}
                  >
                    {!health?.activity_channel?.configured
                      ? 'NOT SET'
                      : health?.activity_channel?.is_ready
                      ? 'READY'
                      : 'DEGRADED'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 1: INVITE DETAILS MODAL */}
      {selectedInviteCode && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#151921] border border-gray-800 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden shadow-2xl animate-scale-up">
            {/* Modal Header */}
            <div className="p-5 border-b border-gray-800 flex items-center justify-between bg-[#12161f]">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-[#5865F2]/10 text-[#5865F2] rounded-xl border border-[#5865F2]/20">
                  <Link2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-white flex items-center gap-2">
                    <span>Invite {selectedInviteCode}</span>
                    {inviteDetails && renderStatusBadge(inviteDetails.invite.status)}
                  </h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Attribution details and joined members list
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedInviteCode(null)}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 custom-scrollbar">
              {detailsLoading || !inviteDetails ? (
                <div className="space-y-4">
                  <LoadingSkeleton rows={4} />
                </div>
              ) : (
                <>
                  {/* Grid Info */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="bg-[#0B0E14] p-3 rounded-xl border border-gray-800">
                      <span className="text-gray-500 block text-[10px] uppercase font-bold">Inviter</span>
                      <span className="font-semibold text-white truncate block mt-0.5">
                        {inviteDetails.invite.inviter_name || 'Server'}
                      </span>
                    </div>
                    <div className="bg-[#0B0E14] p-3 rounded-xl border border-gray-800">
                      <span className="text-gray-500 block text-[10px] uppercase font-bold">Channel</span>
                      <span className="font-semibold text-white truncate block mt-0.5">
                        #{inviteDetails.invite.channel_name || 'unknown'}
                      </span>
                    </div>
                    <div className="bg-[#0B0E14] p-3 rounded-xl border border-gray-800">
                      <span className="text-gray-500 block text-[10px] uppercase font-bold">Discord Uses</span>
                      <span className="font-bold text-gray-200 block mt-0.5">
                        {inviteDetails.invite.uses}
                      </span>
                    </div>
                    <div className="bg-[#0B0E14] p-3 rounded-xl border border-gray-800">
                      <span className="text-gray-500 block text-[10px] uppercase font-bold">Tracked Joins</span>
                      <span className="font-bold text-emerald-400 block mt-0.5">
                        {inviteDetails.total_joins}
                      </span>
                    </div>
                  </div>

                  {/* Joined Members Table */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                      <Users className="w-4 h-4 text-[#5865F2]" />
                      <span>Members Joined Through This Invite</span>
                    </h4>

                    {inviteDetails.joins.length === 0 ? (
                      <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-8 text-center text-gray-500 text-xs">
                        No members have joined through this invite code yet.
                      </div>
                    ) : (
                      <div className="bg-[#0B0E14] border border-gray-800 rounded-xl overflow-hidden">
                        <table className="w-full text-left text-xs">
                          <thead className="bg-[#0e1219] border-b border-gray-800 text-gray-400 font-bold uppercase text-[10px]">
                            <tr>
                              <th className="py-2.5 px-3">Member</th>
                              <th className="py-2.5 px-3">Joined At</th>
                              <th className="py-2.5 px-3">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-gray-800/60 text-gray-300">
                            {inviteDetails.joins.map((j) => (
                              <tr key={j.id} className="hover:bg-gray-800/30">
                                <td className="py-2.5 px-3 font-semibold text-white">
                                  {j.member_name || `User ${j.member_id}`}
                                </td>
                                <td className="py-2.5 px-3 text-gray-400">
                                  {j.joined_at ? new Date(j.joined_at).toLocaleString() : 'Unknown'}
                                </td>
                                <td className="py-2.5 px-3">
                                  {j.is_still_member ? (
                                    <span className="text-emerald-400 text-[11px]">Member</span>
                                  ) : (
                                    <span className="text-gray-500 text-[11px]">Left</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-800 bg-[#12161f] flex items-center justify-between">
              <button
                onClick={() => handleCopy(selectedInviteCode)}
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-xs font-semibold transition-colors"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copy Invite Link</span>
              </button>
              <button
                onClick={() => setSelectedInviteCode(null)}
                className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-xs font-bold transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL 2: USER INVITE PROFILE MODAL */}
      {selectedUserId && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#151921] border border-gray-800 rounded-2xl w-full max-w-xl max-h-[85vh] flex flex-col overflow-hidden shadow-2xl animate-scale-up">
            {/* Header */}
            <div className="p-5 border-b border-gray-800 flex items-center justify-between bg-[#12161f]">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-amber-500/10 text-amber-400 rounded-xl border border-amber-500/20">
                  <User className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-extrabold text-white">
                    Member Invite Profile
                  </h3>
                  <p className="text-xs text-gray-400 mt-0.5">
                    Referral metrics for {userProfile?.username || `User ${selectedUserId}`}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setSelectedUserId(null)}
                className="p-1.5 text-gray-400 hover:text-white rounded-lg hover:bg-gray-800 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 custom-scrollbar">
              {profileLoading || !userProfile ? (
                <div className="space-y-4">
                  <LoadingSkeleton rows={4} />
                </div>
              ) : (
                <>
                  {/* User Profile Card */}
                  <div className="bg-[#0B0E14] border border-gray-800 rounded-2xl p-4 flex items-center gap-4">
                    <div className="w-12 h-12 rounded-2xl bg-[#5865F2] flex items-center justify-center font-black text-white text-lg shadow-md">
                      {userProfile.username.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <h4 className="text-base font-extrabold text-white">
                        {userProfile.username}
                      </h4>
                      <span className="text-xs text-gray-400 font-mono">
                        User ID: {userProfile.user_id}
                      </span>
                    </div>
                  </div>

                  {/* Referral Metrics */}
                  <div className="grid grid-cols-3 gap-3 text-xs">
                    <div className="bg-[#0B0E14] p-3.5 rounded-xl border border-gray-800 text-center">
                      <span className="text-[10px] text-gray-500 uppercase font-bold block">Total Joins</span>
                      <span className="text-2xl font-black text-white block mt-1">
                        {userProfile.total_joins}
                      </span>
                    </div>
                    <div className="bg-[#0B0E14] p-3.5 rounded-xl border border-gray-800 text-center">
                      <span className="text-[10px] text-gray-500 uppercase font-bold block">This Month</span>
                      <span className="text-2xl font-black text-[#858eff] block mt-1">
                        {userProfile.this_month_joins}
                      </span>
                    </div>
                    <div className="bg-[#0B0E14] p-3.5 rounded-xl border border-gray-800 text-center">
                      <span className="text-[10px] text-gray-500 uppercase font-bold block">This Week</span>
                      <span className="text-2xl font-black text-emerald-400 block mt-1">
                        {userProfile.this_week_joins}
                      </span>
                    </div>
                  </div>

                  <div className="bg-[#0B0E14] p-3.5 rounded-xl border border-gray-800 flex items-center justify-between text-xs">
                    <span className="text-gray-400">Current Members in Server:</span>
                    <span className="font-bold text-emerald-400">{userProfile.current_members_referred}</span>
                  </div>
                  <div className="bg-[#0B0E14] p-3.5 rounded-xl border border-gray-800 flex items-center justify-between text-xs">
                    <span className="text-gray-400">Former Members (Left):</span>
                    <span className="font-bold text-gray-400">{userProfile.former_members_referred}</span>
                  </div>

                  {/* Tracked Codes */}
                  <div className="space-y-2">
                    <span className="text-xs font-bold text-gray-400 uppercase tracking-wider block">
                      Invites Created by this Member ({userProfile.invites.length})
                    </span>
                    {userProfile.invites.length === 0 ? (
                      <div className="text-xs text-gray-500 bg-[#0B0E14] p-4 rounded-xl border border-gray-800 text-center">
                        No active invite codes created by this user.
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {userProfile.invites.map((inv) => (
                          <div
                            key={inv.invite_code}
                            className="bg-[#0B0E14] p-3 rounded-xl border border-gray-800 flex items-center justify-between text-xs"
                          >
                            <div className="flex items-center gap-2">
                              <span className="font-mono font-bold text-white bg-gray-900 px-2 py-1 rounded border border-gray-800">
                                {inv.invite_code}
                              </span>
                              <span className="text-gray-400 font-mono text-[11px]">
                                #{inv.channel_name || 'channel'}
                              </span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className="font-bold text-emerald-400">{inv.uses} uses</span>
                              {renderStatusBadge(inv.status)}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-gray-800 bg-[#12161f] flex justify-end">
              <button
                onClick={() => setSelectedUserId(null)}
                className="px-4 py-1.5 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-xs font-bold transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
