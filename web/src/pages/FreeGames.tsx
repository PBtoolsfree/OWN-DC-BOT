import React, { useState, useEffect, useCallback } from 'react';
import {
  Gift,
  RefreshCw,
  Send,
  CheckCircle2,
  Clock,
  ExternalLink,
  ShieldAlert,
  Search,
  Sliders,
  Sparkles,
  Laptop,
  Smartphone,
  Store,
  Calendar,
  Hash,
  Bell,
  Check,
  Zap,
} from 'lucide-react';
import { freegamesApi } from '../api/freegames';
import { channelsApi } from '../api/channels';
import {
  DiscordChannel,
  DiscordRole,
  FreeGameHealth,
  FreeGameOffer,
  FreeGameSettings,
  FreeGameSourceHealth,
  FreeGameStats,
} from '../types';
import { toast } from '../hooks/useToast';
import { LoadingSkeleton } from '../components/LoadingSkeleton';

type TabType = 'overview' | 'offers' | 'sources' | 'settings';

const KNOWN_SOURCES = [
  { id: 'epic', name: 'Epic Games Store', category: 'PC', defaultUrl: 'https://store.epicgames.com' },
  { id: 'steam', name: 'Steam', category: 'PC', defaultUrl: 'https://store.steampowered.com' },
  { id: 'gog', name: 'GOG', category: 'PC', defaultUrl: 'https://www.gog.com' },
  { id: 'google_play', name: 'Google Play', category: 'Mobile', defaultUrl: 'https://play.google.com' },
  { id: 'app_store', name: 'Apple App Store', category: 'Mobile', defaultUrl: 'https://www.apple.com/app-store/' },
];

const OFFER_TYPES = [
  { id: 'free_to_keep', label: 'Free to Keep', desc: '100% discount, claim and keep forever' },
  { id: 'free_dlc', label: 'Free DLC & Addons', desc: 'Expansions and in-game packs' },
  { id: 'free_trial', label: 'Free Weekends / Trials', desc: 'Limited-time free play periods' },
  { id: 'free_to_play', label: 'Free-to-Play', desc: 'New free-to-play launches' },
];

const POLL_INTERVALS = [
  { value: 300, label: 'Every 5 minutes' },
  { value: 900, label: 'Every 15 minutes (Recommended)' },
  { value: 1800, label: 'Every 30 minutes' },
  { value: 3600, label: 'Every 1 hour' },
  { value: 7200, label: 'Every 2 hours' },
  { value: 14400, label: 'Every 4 hours' },
  { value: 86400, label: 'Every 24 hours' },
];

export default function FreeGames() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [testing, setTesting] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  // Data states
  const [stats, setStats] = useState<FreeGameStats | null>(null);
  const [health, setHealth] = useState<FreeGameHealth | null>(null);
  const [sources, setSources] = useState<FreeGameSourceHealth[]>([]);
  const [offers, setOffers] = useState<FreeGameOffer[]>([]);
  const [_settings, setSettings] = useState<FreeGameSettings | null>(null);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);
  const [roles, setRoles] = useState<DiscordRole[]>([]);

  // Filter states for Offers tab
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sourceFilter, setSourceFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Settings form state
  const [formData, setFormData] = useState({
    enabled: true,
    destination_channel_id: '',
    role_mention_id: '',
    poll_interval_seconds: 900,
    enabled_sources: ['epic', 'steam', 'gog', 'google_play', 'app_store'],
    offer_types: ['free_to_keep'],
    ending_soon_enabled: false,
    ending_soon_hours: 24,
    post_thumbnail: true,
    post_description: true,
    show_price: true,
    show_expiry: true,
  });

  // Load all initial data
  const loadData = useCallback(async () => {
    try {
      const [statsRes, healthRes, sourcesRes, offersRes, settingsRes, channelsRes, rolesRes] =
        await Promise.allSettled([
          freegamesApi.getStats(),
          freegamesApi.getHealth(),
          freegamesApi.getSources(),
          freegamesApi.getOffers({ limit: 100 }),
          freegamesApi.getSettings(),
          channelsApi.getChannels(),
          channelsApi.getRoles(),
        ]);

      if (statsRes.status === 'fulfilled') setStats(statsRes.value);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
      if (sourcesRes.status === 'fulfilled') setSources(sourcesRes.value.sources || []);
      if (offersRes.status === 'fulfilled') setOffers(offersRes.value.offers || []);

      if (channelsRes.status === 'fulfilled') {
        const textChannels = (channelsRes.value || []).filter(
          (c) => c.type === 'text' || !c.type
        );
        setChannels(textChannels);
      }

      if (rolesRes.status === 'fulfilled') {
        setRoles(rolesRes.value || []);
      }

      if (settingsRes.status === 'fulfilled' && settingsRes.value) {
        const s = settingsRes.value;
        setSettings(s);

        let parsedSources: string[] = ['epic', 'steam', 'gog', 'google_play', 'app_store'];
        if (typeof s.enabled_sources_json === 'string') {
          try {
            parsedSources = JSON.parse(s.enabled_sources_json);
          } catch (_) {
            parsedSources = ['epic', 'steam', 'gog', 'google_play', 'app_store'];
          }
        } else if (Array.isArray(s.enabled_sources_json)) {
          parsedSources = s.enabled_sources_json;
        }

        let parsedOffers: string[] = ['free_to_keep'];
        if (typeof s.offer_types_json === 'string') {
          try {
            parsedOffers = JSON.parse(s.offer_types_json);
          } catch (_) {
            parsedOffers = ['free_to_keep'];
          }
        } else if (Array.isArray(s.offer_types_json)) {
          parsedOffers = s.offer_types_json;
        }

        setFormData({
          enabled: !!s.enabled,
          destination_channel_id: s.destination_channel_id ? String(s.destination_channel_id) : '',
          role_mention_id: s.role_mention_id ? String(s.role_mention_id) : '',
          poll_interval_seconds: s.poll_interval_seconds || 900,
          enabled_sources: parsedSources,
          offer_types: parsedOffers,
          ending_soon_enabled: !!s.ending_soon_enabled,
          ending_soon_hours: s.ending_soon_hours || 24,
          post_thumbnail: s.post_thumbnail !== false,
          post_description: s.post_description !== false,
          show_price: s.show_price !== false,
          show_expiry: s.show_expiry !== false,
        });
      }
    } catch (err: any) {
      toast.error('Failed to load Free Games telemetry: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Sync Now handler
  const handleSyncNow = async () => {
    setSyncing(true);
    try {
      const res = await freegamesApi.syncOffers();
      if (res.success) {
        toast.success(
          `Offers synchronized! Found ${res.total_found ?? 0} offers (${res.new_offers ?? 0} new).`
        );
        await loadData();
      } else {
        toast.error(res.message || 'Synchronization reported failures.');
      }
    } catch (err: any) {
      toast.error('Sync failed: ' + (err.message || 'Check server logs.'));
    } finally {
      setSyncing(false);
    }
  };

  // Test Notification handler
  const handleTestNotification = async () => {
    setTesting(true);
    try {
      const res = await freegamesApi.testNotification();
      if (res.success) {
        toast.success(res.message || 'Test notification dispatched to Discord channel!');
      } else {
        toast.error(res.message || 'Failed to dispatch test notification.');
      }
    } catch (err: any) {
      toast.error('Test notification failed: ' + (err.message || 'Check bot permissions.'));
    } finally {
      setTesting(false);
    }
  };

  // Save Settings handler
  const handleSaveSettings = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    setSavingSettings(true);
    try {
      const payload: Partial<FreeGameSettings> = {
        enabled: formData.enabled,
        destination_channel_id: formData.destination_channel_id ? formData.destination_channel_id : null,
        role_mention_id: formData.role_mention_id ? formData.role_mention_id : null,
        poll_interval_seconds: Number(formData.poll_interval_seconds),
        enabled_sources_json: formData.enabled_sources,
        offer_types_json: formData.offer_types,
        ending_soon_enabled: formData.ending_soon_enabled,
        ending_soon_hours: Number(formData.ending_soon_hours),
        post_thumbnail: formData.post_thumbnail,
        post_description: formData.post_description,
        show_price: formData.show_price,
        show_expiry: formData.show_expiry,
      };

      const res = await freegamesApi.updateSettings(payload);
      if (res.success) {
        toast.success('Free Games tracker settings saved successfully!');
        setSettings(res.settings);
        await loadData();
      } else {
        toast.error('Could not save settings.');
      }
    } catch (err: any) {
      toast.error('Failed to save settings: ' + (err.message || 'Server error'));
    } finally {
      setSavingSettings(false);
    }
  };

  // Filtered offers list
  const filteredOffers = offers.filter((o) => {
    const matchesStatus =
      statusFilter === 'ALL' || o.status.toUpperCase() === statusFilter.toUpperCase();
    const matchesSource =
      sourceFilter === 'ALL' || o.source.toLowerCase() === sourceFilter.toLowerCase();
    const matchesSearch =
      !searchQuery.trim() ||
      o.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.store_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      o.platform.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesStatus && matchesSource && matchesSearch;
  });

  // Calculate overview metrics (fallback to computed if stats missing)
  const totalOffersCount = stats?.total_offers ?? offers.length;
  const activeOffersCount =
    stats?.active_offers ??
    offers.filter((o) => ['ACTIVE', 'NEW', 'ENDING_SOON'].includes(o.status.toUpperCase())).length;

  const now = new Date();
  const postedTodayCount =
    stats?.posted_today ??
    offers.filter((o) => {
      if (!o.last_posted_at) return false;
      const posted = new Date(o.last_posted_at);
      return posted.toDateString() === now.toDateString();
    }).length;

  const endingSoonCount =
    stats?.ending_soon ??
    offers.filter((o) => {
      if (o.status.toUpperCase() === 'ENDING_SOON') return true;
      if (!o.ends_at) return false;
      const ends = new Date(o.ends_at);
      const diffHours = (ends.getTime() - now.getTime()) / (1000 * 60 * 60);
      return diffHours > 0 && diffHours <= 48;
    }).length;

  const healthySourcesCount = sources.filter((s) => s.status === 'HEALTHY').length;
  const totalSourcesCount = sources.length || KNOWN_SOURCES.length;

  // Format expiry string
  const formatExpiry = (endsAt: string | null) => {
    if (!endsAt) return 'Permanent / No expiry';
    try {
      const d = new Date(endsAt);
      const diffMs = d.getTime() - Date.now();
      if (diffMs <= 0) return 'Expired';
      const hours = Math.floor(diffMs / (1000 * 60 * 60));
      const days = Math.floor(hours / 24);
      if (days > 1) {
        return `Ends in ${days} days (${d.toLocaleDateString()})`;
      } else if (hours > 0) {
        return `Ends in ${hours} hours`;
      } else {
        const mins = Math.max(1, Math.floor(diffMs / (1000 * 60)));
        return `Ends in ${mins} mins`;
      }
    } catch (_) {
      return endsAt;
    }
  };

  const renderStatusBadge = (status: string) => {
    const s = status.toUpperCase();
    if (s === 'ACTIVE') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          ACTIVE
        </span>
      );
    }
    if (s === 'ENDING_SOON') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <Clock className="w-3 h-3 text-amber-400" />
          ENDING SOON
        </span>
      );
    }
    if (s === 'NEW') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
          <Sparkles className="w-3 h-3 text-indigo-400" />
          NEW
        </span>
      );
    }
    if (s === 'EXPIRED') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-gray-700/50 text-gray-400 border border-gray-600/30">
          EXPIRED
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-gray-800 text-gray-300">
        {status}
      </span>
    );
  };

  const getStoreBadge = (storeName: string, source: string) => {
    const lower = (source || storeName).toLowerCase();
    if (lower.includes('epic')) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-800 text-white border border-slate-700">
          <Store className="w-3 h-3 text-white" />
          Epic Games
        </span>
      );
    }
    if (lower.includes('steam')) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-blue-950/60 text-sky-400 border border-sky-800/40">
          <Laptop className="w-3 h-3 text-sky-400" />
          Steam
        </span>
      );
    }
    if (lower.includes('gog')) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-950/60 text-purple-300 border border-purple-800/40">
          <Store className="w-3 h-3 text-purple-400" />
          GOG
        </span>
      );
    }
    if (lower.includes('google') || lower.includes('android')) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800/40">
          <Smartphone className="w-3 h-3 text-emerald-400" />
          Google Play
        </span>
      );
    }
    if (lower.includes('apple') || lower.includes('ios')) {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-zinc-800 text-zinc-200 border border-zinc-700">
          <Smartphone className="w-3 h-3 text-zinc-300" />
          App Store
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[10px] font-bold bg-gray-800 text-gray-300 border border-gray-700">
        <Store className="w-3 h-3" />
        {storeName}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="space-y-6 max-w-7xl mx-auto">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-[#151921] rounded-2xl animate-pulse" />
          <div className="space-y-2">
            <div className="w-48 h-6 bg-[#151921] rounded animate-pulse" />
            <div className="w-72 h-4 bg-[#151921] rounded animate-pulse" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-28 bg-[#151921] border border-gray-800 rounded-2xl animate-pulse" />
          ))}
        </div>
        <LoadingSkeleton rows={6} />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-pink-500/10 border border-pink-500/20 rounded-2xl text-pink-400 shadow-lg shadow-pink-500/5">
              <Gift className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                <span>Free Games & Deals Tracker</span>
                {formData.enabled ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    ENABLED
                  </span>
                ) : (
                  <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-bold bg-gray-800 text-gray-400 border border-gray-700">
                    PAUSED
                  </span>
                )}
              </h1>
              <p className="text-xs text-gray-400 mt-1">
                Automated multi-store free games aggregator, canonical claim resolver, and Discord alerts.
              </p>
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div className="flex items-center gap-3 self-start md:self-auto">
          <button
            type="button"
            onClick={handleSyncNow}
            disabled={syncing}
            className="inline-flex items-center gap-2 px-4 py-2 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl transition-all shadow-md shadow-[#5865F2]/20 disabled:opacity-50"
            title="Scan all enabled game stores for free offers immediately"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Syncing Offers...' : 'Sync Now'}</span>
          </button>

          <button
            type="button"
            onClick={handleTestNotification}
            disabled={testing || !formData.destination_channel_id}
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-xs font-bold rounded-xl transition-all border border-gray-700 disabled:opacity-50"
            title={
              formData.destination_channel_id
                ? 'Send a demo embed with claim button to Discord'
                : 'Select a destination channel in Settings first'
            }
          >
            <Send className={`w-3.5 h-3.5 ${testing ? 'animate-pulse text-pink-400' : ''}`} />
            <span>{testing ? 'Sending...' : 'Test Notification'}</span>
          </button>
        </div>
      </div>

      {/* Permission or Configuration Warning Banner */}
      {!formData.destination_channel_id && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-2xl p-4 text-amber-200 text-xs flex items-start gap-3">
          <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="flex-1 space-y-1">
            <span className="font-bold text-sm block text-amber-300">
              Destination Channel Not Configured
            </span>
            <p className="text-amber-200/90 leading-relaxed">
              New free game offers cannot be posted to Discord until a channel is selected. Open the{' '}
              <button
                type="button"
                onClick={() => setActiveTab('settings')}
                className="underline font-bold hover:text-white"
              >
                Settings tab
              </button>{' '}
              to choose your destination channel.
            </p>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="border-b border-gray-800 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <button
            type="button"
            data-testid="tab-overview"
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'overview'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Sparkles className="w-4 h-4" />
            <span>Overview</span>
          </button>

          <button
            type="button"
            data-testid="tab-offers"
            onClick={() => setActiveTab('offers')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'offers'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Gift className="w-4 h-4" />
            <span>Offers</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-gray-800 text-[10px] text-gray-400">
              {offers.length}
            </span>
          </button>

          <button
            type="button"
            data-testid="tab-sources"
            onClick={() => setActiveTab('sources')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'sources'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Store className="w-4 h-4" />
            <span>Sources</span>
            <span className="ml-1 px-1.5 py-0.5 rounded-full bg-gray-800 text-[10px] text-gray-400">
              {sources.length || KNOWN_SOURCES.length}
            </span>
          </button>

          <button
            type="button"
            data-testid="tab-settings"
            onClick={() => setActiveTab('settings')}
            className={`flex items-center gap-2 px-4 py-3 text-xs font-bold border-b-2 transition-all ${
              activeTab === 'settings'
                ? 'border-[#5865F2] text-[#858eff] bg-[#5865F2]/5'
                : 'border-transparent text-gray-400 hover:text-white hover:bg-gray-800/20'
            }`}
          >
            <Sliders className="w-4 h-4" />
            <span>Settings</span>
          </button>
        </div>
      </div>

      {/* ─── TAB 1: OVERVIEW ─────────────────────────────────────────── */}
      {activeTab === 'overview' && (
        <div className="space-y-6 animate-fade-in">
          {/* Overview Top Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
            {/* Total Offers */}
            <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
                <span>Total Offers</span>
                <Gift className="w-4 h-4 text-pink-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black text-white tracking-tight">
                  {totalOffersCount}
                </span>
                <span className="text-xs text-gray-400 font-semibold">tracked</span>
              </div>
              <span className="text-[11px] text-gray-500 mt-1 block">
                Aggregated across all stores
              </span>
            </div>

            {/* Active Offers */}
            <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
                <span>Active Offers</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black text-emerald-400 tracking-tight">
                  {activeOffersCount}
                </span>
                <span className="text-xs text-emerald-400/80 font-semibold">claimable</span>
              </div>
              <span className="text-[11px] text-gray-500 mt-1 block">
                Currently 100% free right now
              </span>
            </div>

            {/* Posted Today */}
            <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
                <span>Posted Today</span>
                <Send className="w-4 h-4 text-sky-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black text-sky-400 tracking-tight">
                  {postedTodayCount}
                </span>
                <span className="text-xs text-gray-400 font-semibold">alerts</span>
              </div>
              <span className="text-[11px] text-gray-500 mt-1 block">
                Dispatched to Discord today
              </span>
            </div>

            {/* Ending Soon */}
            <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
                <span>Ending Soon</span>
                <Clock className="w-4 h-4 text-amber-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black text-amber-400 tracking-tight">
                  {endingSoonCount}
                </span>
                <span className="text-xs text-amber-400/80 font-semibold">urgent</span>
              </div>
              <span className="text-[11px] text-gray-500 mt-1 block">
                Expiring in &lt; 48 hours
              </span>
            </div>

            {/* Source Health */}
            <div className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg relative overflow-hidden group hover:border-gray-700 transition-all">
              <div className="flex items-center justify-between text-gray-400 text-xs font-bold uppercase tracking-wider">
                <span>Source Health</span>
                <Zap className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="text-3xl font-black text-indigo-400 tracking-tight">
                  {healthySourcesCount}/{totalSourcesCount}
                </span>
                <span className="text-xs text-gray-400 font-semibold">healthy</span>
              </div>
              <span className="text-[11px] text-gray-500 mt-1 block">
                Store adapters operational
              </span>
            </div>
          </div>

          {/* Subsystem Health & Channel Status Row */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Store className="w-4 h-4 text-[#5865F2]" />
                  <span className="text-xs font-bold uppercase tracking-wider text-white">
                    Subsystem Status
                  </span>
                </div>
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                    health?.healthy !== false
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      health?.healthy !== false ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                    }`}
                  />
                  {health?.healthy !== false ? 'ALL SERVICES OK' : 'DEGRADED'}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="bg-[#0B0E14] border border-gray-800/80 rounded-xl p-3">
                  <span className="text-gray-400 block text-[11px]">Scheduler Status</span>
                  <span className="font-bold text-white mt-1 block">
                    {health?.scheduler_running !== false ? 'Running (Active)' : 'Stopped'}
                  </span>
                </div>
                <div className="bg-[#0B0E14] border border-gray-800/80 rounded-xl p-3">
                  <span className="text-gray-400 block text-[11px]">Polling Interval</span>
                  <span className="font-bold text-white mt-1 block">
                    {Math.round((formData.poll_interval_seconds || 900) / 60)} minutes
                  </span>
                </div>
              </div>
            </div>

            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bell className="w-4 h-4 text-pink-400" />
                  <span className="text-xs font-bold uppercase tracking-wider text-white">
                    Discord Destination
                  </span>
                </div>
                <span
                  className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                    formData.destination_channel_id
                      ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  }`}
                >
                  {formData.destination_channel_id ? 'CONFIGURED' : 'UNCONFIGURED'}
                </span>
              </div>

              <div className="bg-[#0B0E14] border border-gray-800/80 rounded-xl p-3 text-xs flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Hash className="w-4 h-4 text-gray-400" />
                  <span className="text-gray-300 font-semibold truncate">
                    {channels.find((c) => String(c.id) === String(formData.destination_channel_id))
                      ?.name ||
                      (formData.destination_channel_id
                        ? `Channel ID: ${formData.destination_channel_id}`
                        : 'No destination channel selected')}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveTab('settings')}
                  className="text-xs text-[#858eff] hover:underline font-bold"
                >
                  Configure
                </button>
              </div>
            </div>
          </div>

          {/* Quick Active Highlights */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-lg space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-pink-400" />
                  <span>Currently Active Free Games</span>
                </h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Top claimed free games across Epic, Steam, GOG, and mobile stores.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActiveTab('offers')}
                className="text-xs font-bold text-[#858eff] hover:text-white transition-colors"
              >
                View All Offers ({offers.length}) &rarr;
              </button>
            </div>

            {offers.length === 0 ? (
              <div className="text-center py-8 text-gray-500 text-xs">
                No offers tracked yet. Click{' '}
                <button
                  type="button"
                  onClick={handleSyncNow}
                  className="text-[#858eff] font-bold underline"
                >
                  Sync Now
                </button>{' '}
                to poll game stores.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {offers.slice(0, 6).map((offer) => {
                  const claimLink = offer.canonical_claim_url || offer.claim_url;
                  return (
                    <div
                      key={offer.id}
                      className="bg-[#0B0E14] border border-gray-800/80 rounded-xl p-4 flex flex-col justify-between hover:border-gray-700 transition-all group"
                    >
                      <div className="space-y-3">
                        <div className="relative aspect-video rounded-lg overflow-hidden bg-gray-900 border border-gray-800">
                          {offer.thumbnail_url ? (
                            <img
                              src={offer.thumbnail_url}
                              alt={offer.title}
                              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                              onError={(e) => {
                                (e.target as HTMLElement).style.display = 'none';
                              }}
                            />
                          ) : (
                            <div className="w-full h-full flex items-center justify-center text-gray-600">
                              <Gift className="w-8 h-8 text-gray-700" />
                            </div>
                          )}
                          <div className="absolute top-2 left-2 flex gap-1">
                            {getStoreBadge(offer.store_name, offer.source)}
                          </div>
                          <div className="absolute top-2 right-2">
                            {renderStatusBadge(offer.status)}
                          </div>
                        </div>

                        <div>
                          <h4 className="font-bold text-white text-sm line-clamp-1 group-hover:text-pink-400 transition-colors">
                            {offer.title}
                          </h4>
                          <div className="flex items-center gap-2 mt-1 text-xs">
                            <span className="text-emerald-400 font-extrabold uppercase">
                              100% FREE
                            </span>
                            {offer.original_price && offer.original_price > 0 && (
                              <span className="text-gray-500 line-through text-[11px]">
                                ${offer.original_price.toFixed(2)}
                              </span>
                            )}
                            <span className="text-gray-500">&bull;</span>
                            <span className="text-gray-400 text-[11px]">{offer.platform}</span>
                          </div>
                          <div className="flex items-center gap-1.5 text-[11px] text-gray-400 mt-2">
                            <Clock className="w-3 h-3 text-amber-400" />
                            <span>{formatExpiry(offer.ends_at)}</span>
                          </div>
                        </div>
                      </div>

                      <div className="mt-4 pt-3 border-t border-gray-800/80 flex items-center justify-between">
                        <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                          {offer.offer_type.replace(/_/g, ' ')}
                        </span>
                        <a
                          href={claimLink}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white text-xs font-black rounded-lg transition-all shadow-md shadow-pink-500/20"
                        >
                          <Gift className="w-3.5 h-3.5" />
                          <span>🎁 CLAIM GAME</span>
                        </a>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ─── TAB 2: OFFERS ───────────────────────────────────────────── */}
      {activeTab === 'offers' && (
        <div className="space-y-6 animate-fade-in">
          {/* Offers Filter Bar */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 relative">
              <Search className="w-4 h-4 text-gray-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search games, stores, platforms..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl pl-10 pr-4 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2]"
              />
            </div>

            <div className="flex flex-wrap items-center gap-3">
              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-[#0B0E14] border border-gray-800 text-xs font-semibold text-gray-300 rounded-xl px-3 py-2 focus:outline-none focus:border-[#5865F2]"
              >
                <option value="ALL">All Statuses</option>
                <option value="ACTIVE">Active</option>
                <option value="NEW">New</option>
                <option value="ENDING_SOON">Ending Soon</option>
                <option value="EXPIRED">Expired</option>
              </select>

              {/* Source Filter */}
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="bg-[#0B0E14] border border-gray-800 text-xs font-semibold text-gray-300 rounded-xl px-3 py-2 focus:outline-none focus:border-[#5865F2]"
              >
                <option value="ALL">All Stores</option>
                <option value="epic">Epic Games Store</option>
                <option value="steam">Steam</option>
                <option value="gog">GOG</option>
                <option value="google_play">Google Play</option>
                <option value="app_store">Apple App Store</option>
              </select>

              <button
                type="button"
                onClick={handleSyncNow}
                disabled={syncing}
                className="inline-flex items-center gap-1.5 px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 text-xs font-bold rounded-xl transition-all border border-gray-700"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin text-pink-400' : ''}`} />
                <span>Refresh</span>
              </button>
            </div>
          </div>

          {/* Offers Table / Card List */}
          {filteredOffers.length === 0 ? (
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-12 text-center space-y-3">
              <Gift className="w-10 h-10 text-gray-600 mx-auto" />
              <h3 className="text-base font-bold text-white">No Offers Found</h3>
              <p className="text-xs text-gray-400 max-w-sm mx-auto">
                No free game offers match your current search or filter criteria. Try clearing filters
                or click Sync Now to check store endpoints.
              </p>
              <button
                type="button"
                onClick={() => {
                  setSearchQuery('');
                  setStatusFilter('ALL');
                  setSourceFilter('ALL');
                }}
                className="px-4 py-2 bg-gray-800 text-gray-300 hover:text-white text-xs font-bold rounded-xl transition-colors"
              >
                Clear Filters
              </button>
            </div>
          ) : (
            <div className="bg-[#151921] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-gray-800 bg-[#12161f]/60 text-gray-400 text-[11px] font-bold uppercase tracking-wider">
                      <th className="py-3 px-4">Game</th>
                      <th className="py-3 px-4">Store</th>
                      <th className="py-3 px-4">Platform</th>
                      <th className="py-3 px-4">Offer Type</th>
                      <th className="py-3 px-4">Price</th>
                      <th className="py-3 px-4">Expiry</th>
                      <th className="py-3 px-4">Status</th>
                      <th className="py-3 px-4 text-right">Claim</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 text-xs">
                    {filteredOffers.map((offer) => {
                      const canonicalClaimUrl = offer.canonical_claim_url || offer.claim_url;
                      return (
                        <tr
                          key={offer.id}
                          className="hover:bg-gray-800/30 transition-colors group"
                        >
                          {/* Thumbnail & Game Title */}
                          <td className="py-3.5 px-4">
                            <div className="flex items-center gap-3">
                              <div className="w-14 h-10 rounded-lg overflow-hidden bg-gray-900 border border-gray-800 shrink-0">
                                {offer.thumbnail_url ? (
                                  <img
                                    src={offer.thumbnail_url}
                                    alt={offer.title}
                                    className="w-full h-full object-cover"
                                    onError={(e) => {
                                      (e.target as HTMLElement).style.display = 'none';
                                    }}
                                  />
                                ) : (
                                  <div className="w-full h-full flex items-center justify-center text-gray-600">
                                    <Gift className="w-4 h-4 text-gray-700" />
                                  </div>
                                )}
                              </div>
                              <div className="min-w-0 max-w-xs">
                                <span className="font-bold text-white block truncate group-hover:text-pink-400 transition-colors">
                                  {offer.title}
                                </span>
                                {offer.description && (
                                  <span className="text-[11px] text-gray-500 block truncate">
                                    {offer.description}
                                  </span>
                                )}
                              </div>
                            </div>
                          </td>

                          {/* Store */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            {getStoreBadge(offer.store_name, offer.source)}
                          </td>

                          {/* Platform */}
                          <td className="py-3.5 px-4 whitespace-nowrap text-gray-300 font-semibold">
                            <span className="inline-flex items-center gap-1">
                              {offer.platform.toLowerCase().includes('mobile') ||
                              offer.platform.toLowerCase().includes('android') ||
                              offer.platform.toLowerCase().includes('ios') ? (
                                <Smartphone className="w-3.5 h-3.5 text-gray-400" />
                              ) : (
                                <Laptop className="w-3.5 h-3.5 text-gray-400" />
                              )}
                              <span>{offer.platform}</span>
                            </span>
                          </td>

                          {/* Offer Type */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gray-800 text-gray-300">
                              {offer.offer_type.replace(/_/g, ' ')}
                            </span>
                          </td>

                          {/* Price */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            <div className="flex items-baseline gap-1.5">
                              <span className="text-emerald-400 font-black">FREE</span>
                              {offer.original_price && offer.original_price > 0 && (
                                <span className="line-through text-gray-500 text-[11px]">
                                  ${offer.original_price.toFixed(2)}
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Expiry */}
                          <td className="py-3.5 px-4 whitespace-nowrap text-gray-400 text-[11px]">
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3 text-gray-500" />
                              <span>{formatExpiry(offer.ends_at)}</span>
                            </span>
                          </td>

                          {/* Status */}
                          <td className="py-3.5 px-4 whitespace-nowrap">
                            {renderStatusBadge(offer.status)}
                          </td>

                          {/* CLAIM GAME BUTTON (Uses Canonical Claim URL) */}
                          <td className="py-3.5 px-4 whitespace-nowrap text-right">
                            <a
                              href={canonicalClaimUrl}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-pink-500 to-rose-500 hover:from-pink-600 hover:to-rose-600 text-white text-xs font-black rounded-lg transition-all shadow-md shadow-pink-500/20 active:scale-95"
                              title={`Claim canonical offer from ${offer.store_name}`}
                            >
                              <Gift className="w-3.5 h-3.5" />
                              <span>🎁 CLAIM GAME</span>
                            </a>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── TAB 3: SOURCES ──────────────────────────────────────────── */}
      {activeTab === 'sources' && (
        <div className="space-y-6 animate-fade-in">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <Store className="w-5 h-5 text-indigo-400" />
                <span>Store Adapters & Integration Health</span>
              </h3>
              <p className="text-xs text-gray-400 mt-0.5">
                Real-time operational status, latency diagnostics, and active offer count per source adapter.
              </p>
            </div>

            <button
              type="button"
              onClick={handleSyncNow}
              disabled={syncing}
              className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-xs font-bold rounded-xl transition-all border border-gray-700 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin text-[#5865F2]' : ''}`} />
              <span>{syncing ? 'Scanning...' : 'Poll All Sources'}</span>
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {KNOWN_SOURCES.map((known) => {
              const srcData = sources.find(
                (s) =>
                  s.source_name?.toLowerCase() === known.id ||
                  s.source?.toLowerCase() === known.id
              );

              const status = srcData?.status || 'HEALTHY';
              const offerCount = srcData?.offer_count ?? offers.filter((o) => o.source === known.id).length;
              const latency = srcData?.response_latency_ms ?? srcData?.latency_ms ?? null;
              const lastChecked = srcData?.last_checked_at;
              const isEnabled = formData.enabled_sources.includes(known.id);

              return (
                <div
                  key={known.id}
                  className="bg-[#151921] border border-gray-800/80 rounded-2xl p-5 shadow-lg space-y-4 hover:border-gray-700 transition-all flex flex-col justify-between"
                >
                  <div className="space-y-3">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-2.5 bg-gray-800/80 border border-gray-700/60 rounded-xl">
                          {known.category === 'PC' ? (
                            <Laptop className="w-5 h-5 text-indigo-400" />
                          ) : (
                            <Smartphone className="w-5 h-5 text-emerald-400" />
                          )}
                        </div>
                        <div>
                          <h4 className="font-bold text-white text-sm flex items-center gap-2">
                            <span>{known.name}</span>
                          </h4>
                          <span className="text-[10px] text-gray-500 font-semibold tracking-wide uppercase">
                            {known.category} Store Adapter
                          </span>
                        </div>
                      </div>

                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                          status === 'HEALTHY'
                            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                            : status === 'DEGRADED'
                            ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            status === 'HEALTHY'
                              ? 'bg-emerald-400 animate-pulse'
                              : status === 'DEGRADED'
                              ? 'bg-amber-400'
                              : 'bg-rose-400'
                          }`}
                        />
                        {status}
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-[#0B0E14] border border-gray-800/80 rounded-xl p-2.5">
                        <span className="text-[10px] text-gray-500 uppercase font-bold block">
                          Offers Discovered
                        </span>
                        <span className="text-base font-black text-white mt-0.5 block">
                          {offerCount}
                        </span>
                      </div>

                      <div className="bg-[#0B0E14] border border-gray-800/80 rounded-xl p-2.5">
                        <span className="text-[10px] text-gray-500 uppercase font-bold block">
                          Response Latency
                        </span>
                        <span className="text-base font-black text-white mt-0.5 block">
                          {latency ? `${Math.round(latency)} ms` : '--'}
                        </span>
                      </div>
                    </div>

                    <div className="space-y-1 text-[11px] text-gray-400">
                      <div className="flex items-center justify-between">
                        <span>Tracker Polling:</span>
                        <span
                          className={`font-semibold ${
                            isEnabled ? 'text-emerald-400' : 'text-gray-500'
                          }`}
                        >
                          {isEnabled ? 'Enabled' : 'Disabled in settings'}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span>Last Verified:</span>
                        <span className="text-gray-300">
                          {lastChecked ? new Date(lastChecked).toLocaleTimeString() : 'Recently'}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="pt-3 border-t border-gray-800/80 flex items-center justify-between">
                    <a
                      href={known.defaultUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-gray-400 hover:text-white inline-flex items-center gap-1 font-semibold transition-colors"
                    >
                      <ExternalLink className="w-3 h-3" />
                      <span>Official Store</span>
                    </a>

                    <button
                      type="button"
                      onClick={() => {
                        setSourceFilter(known.id);
                        setActiveTab('offers');
                      }}
                      className="text-xs text-[#858eff] hover:underline font-bold"
                    >
                      View Deals &rarr;
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ─── TAB 4: SETTINGS ─────────────────────────────────────────── */}
      {activeTab === 'settings' && (
        <form onSubmit={handleSaveSettings} className="space-y-6 animate-fade-in">
          {/* Main Toggle Switch */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-lg flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-pink-500/10 border border-pink-500/20 rounded-2xl text-pink-400">
                <Gift className="w-6 h-6" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Enable Free Games Tracker</h3>
                <p className="text-xs text-gray-400 mt-0.5">
                  Automatically poll supported stores and broadcast newly detected free games to Discord.
                </p>
              </div>
            </div>

            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={formData.enabled}
                onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                className="sr-only peer"
              />
              <div className="w-14 h-7 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[4px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-6 after:w-6 after:transition-all peer-checked:bg-emerald-500"></div>
            </label>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Delivery & Discord Channel Settings */}
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-lg space-y-5">
              <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
                <Bell className="w-4 h-4 text-pink-400" />
                <h4 className="text-sm font-bold text-white uppercase tracking-wider">
                  Discord Delivery
                </h4>
              </div>

              {/* Destination Channel Picker */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-gray-300">
                  Destination Text Channel
                </label>
                <div className="relative">
                  <select
                    value={formData.destination_channel_id}
                    onChange={(e) =>
                      setFormData({ ...formData, destination_channel_id: e.target.value })
                    }
                    className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                  >
                    <option value="">Select a channel...</option>
                    {channels.map((ch) => (
                      <option key={ch.id} value={ch.id}>
                        #{ch.name} {ch.category ? `(${ch.category})` : ''}
                      </option>
                    ))}
                  </select>
                </div>
                <p className="text-[11px] text-gray-500">
                  Discord channel where free game alert embeds will be posted.
                </p>
              </div>

              {/* Role Mention Picker */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-gray-300">
                  Role Notification Mention
                </label>
                <select
                  value={formData.role_mention_id}
                  onChange={(e) =>
                    setFormData({ ...formData, role_mention_id: e.target.value })
                  }
                  className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                >
                  <option value="">No mention (Silent alert)</option>
                  {roles.map((r) => (
                    <option key={r.id} value={r.id}>
                      @{r.name}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-gray-500">
                  Optional role pinged when a brand-new free offer is detected.
                </p>
              </div>

              {/* Polling Interval */}
              <div className="space-y-2">
                <label className="block text-xs font-bold text-gray-300">
                  Polling Interval
                </label>
                <select
                  value={formData.poll_interval_seconds}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      poll_interval_seconds: Number(e.target.value),
                    })
                  }
                  className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3.5 py-2.5 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                >
                  {POLL_INTERVALS.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </select>
                <p className="text-[11px] text-gray-500">
                  Frequency the backend checks stores for new and updated offers.
                </p>
              </div>

              {/* Ending Soon Alert Toggle */}
              <div className="pt-2 border-t border-gray-800/80 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-xs font-bold text-white block">
                      Ending-Soon Reminder Alerts
                    </span>
                    <span className="text-[11px] text-gray-500 block">
                      Send a reminder before an active free offer expires
                    </span>
                  </div>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={formData.ending_soon_enabled}
                      onChange={(e) =>
                        setFormData({ ...formData, ending_soon_enabled: e.target.checked })
                      }
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#5865F2]"></div>
                  </label>
                </div>

                {formData.ending_soon_enabled && (
                  <div className="space-y-1 pl-3 border-l-2 border-[#5865F2]">
                    <label className="block text-[11px] font-bold text-gray-400">
                      Alert Window (Hours before expiry)
                    </label>
                    <select
                      value={formData.ending_soon_hours}
                      onChange={(e) =>
                        setFormData({
                          ...formData,
                          ending_soon_hours: Number(e.target.value),
                        })
                      }
                      className="w-full bg-[#0B0E14] border border-gray-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
                    >
                      <option value={12}>12 hours before expiry</option>
                      <option value={24}>24 hours before expiry (Default)</option>
                      <option value={48}>48 hours before expiry</option>
                    </select>
                  </div>
                )}
              </div>
            </div>

            {/* Store Sources & Offer Types Filters */}
            <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-lg space-y-5">
              <div className="flex items-center gap-2 border-b border-gray-800 pb-3">
                <Store className="w-4 h-4 text-emerald-400" />
                <h4 className="text-sm font-bold text-white uppercase tracking-wider">
                  Store Sources & Offer Types
                </h4>
              </div>

              {/* Store Sources Checkboxes */}
              <div className="space-y-3">
                <label className="block text-xs font-bold text-gray-300">
                  Tracked Store Sources
                </label>
                <div className="space-y-2">
                  {KNOWN_SOURCES.map((source) => {
                    const checked = formData.enabled_sources.includes(source.id);
                    return (
                      <label
                        key={source.id}
                        className={`flex items-center justify-between p-2.5 rounded-xl border cursor-pointer transition-colors ${
                          checked
                            ? 'bg-[#0B0E14] border-gray-700 text-white'
                            : 'bg-[#0B0E14]/40 border-gray-800/80 text-gray-400'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              const newSources = e.target.checked
                                ? [...formData.enabled_sources, source.id]
                                : formData.enabled_sources.filter((s) => s !== source.id);
                              setFormData({ ...formData, enabled_sources: newSources });
                            }}
                            className="rounded bg-gray-800 border-gray-700 text-[#5865F2] focus:ring-0"
                          />
                          <span className="text-xs font-bold">{source.name}</span>
                        </div>
                        <span className="text-[10px] text-gray-500 uppercase font-semibold">
                          {source.category}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Offer Types Checkboxes */}
              <div className="space-y-3 pt-2 border-t border-gray-800/80">
                <label className="block text-xs font-bold text-gray-300">
                  Eligible Offer Types
                </label>
                <div className="space-y-2">
                  {OFFER_TYPES.map((type) => {
                    const checked = formData.offer_types.includes(type.id);
                    return (
                      <label
                        key={type.id}
                        className={`flex items-start gap-2.5 p-2.5 rounded-xl border cursor-pointer transition-colors ${
                          checked
                            ? 'bg-[#0B0E14] border-gray-700 text-white'
                            : 'bg-[#0B0E14]/40 border-gray-800/80 text-gray-400'
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const newTypes = e.target.checked
                              ? [...formData.offer_types, type.id]
                              : formData.offer_types.filter((t) => t !== type.id);
                            setFormData({ ...formData, offer_types: newTypes });
                          }}
                          className="mt-0.5 rounded bg-gray-800 border-gray-700 text-[#5865F2] focus:ring-0"
                        />
                        <div>
                          <span className="text-xs font-bold block">{type.label}</span>
                          <span className="text-[10px] text-gray-500 block">{type.desc}</span>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Display Options Toggles */}
              <div className="space-y-3 pt-2 border-t border-gray-800/80">
                <label className="block text-xs font-bold text-gray-300">
                  Embed Display Options
                </label>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <label className="flex items-center gap-2 cursor-pointer bg-[#0B0E14] p-2 rounded-lg border border-gray-800">
                    <input
                      type="checkbox"
                      checked={formData.post_thumbnail}
                      onChange={(e) =>
                        setFormData({ ...formData, post_thumbnail: e.target.checked })
                      }
                      className="rounded bg-gray-800 border-gray-700 text-[#5865F2]"
                    />
                    <span className="text-gray-300 font-semibold text-[11px]">Show Thumbnail</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer bg-[#0B0E14] p-2 rounded-lg border border-gray-800">
                    <input
                      type="checkbox"
                      checked={formData.post_description}
                      onChange={(e) =>
                        setFormData({ ...formData, post_description: e.target.checked })
                      }
                      className="rounded bg-gray-800 border-gray-700 text-[#5865F2]"
                    />
                    <span className="text-gray-300 font-semibold text-[11px]">Show Description</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer bg-[#0B0E14] p-2 rounded-lg border border-gray-800">
                    <input
                      type="checkbox"
                      checked={formData.show_price}
                      onChange={(e) =>
                        setFormData({ ...formData, show_price: e.target.checked })
                      }
                      className="rounded bg-gray-800 border-gray-700 text-[#5865F2]"
                    />
                    <span className="text-gray-300 font-semibold text-[11px]">Show Original Price</span>
                  </label>

                  <label className="flex items-center gap-2 cursor-pointer bg-[#0B0E14] p-2 rounded-lg border border-gray-800">
                    <input
                      type="checkbox"
                      checked={formData.show_expiry}
                      onChange={(e) =>
                        setFormData({ ...formData, show_expiry: e.target.checked })
                      }
                      className="rounded bg-gray-800 border-gray-700 text-[#5865F2]"
                    />
                    <span className="text-gray-300 font-semibold text-[11px]">Show Expiry Date</span>
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* Form Actions Footer */}
          <div className="bg-[#151921] border border-gray-800 rounded-2xl p-5 shadow-lg flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handleTestNotification}
                disabled={testing || !formData.destination_channel_id}
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white text-xs font-bold rounded-xl transition-all border border-gray-700 disabled:opacity-50"
              >
                <Send className={`w-3.5 h-3.5 ${testing ? 'animate-pulse text-pink-400' : ''}`} />
                <span>Test Notification</span>
              </button>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="submit"
                disabled={savingSettings}
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#5865F2] hover:bg-[#4752c4] text-white text-xs font-bold rounded-xl transition-all shadow-lg shadow-[#5865F2]/20 disabled:opacity-50"
              >
                <Check className={`w-4 h-4 ${savingSettings ? 'animate-spin' : ''}`} />
                <span>{savingSettings ? 'Saving Changes...' : 'Save Settings'}</span>
              </button>
            </div>
          </div>
        </form>
      )}
    </div>
  );
}
