import React, { useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Youtube,
  Shield,
  Hash,
  Lock,
  Cpu,
  LogOut,
  ChevronDown,
  ChevronRight,
  Server,
  Bell,
  Sliders,
  FileText,
  Bookmark,
  ScrollText,
  ListTree,
  ShieldAlert,
  Zap,
  AlertTriangle,
  UserPlus,
} from 'lucide-react';

interface SidebarProps {
  guildId?: string;
  onLogout: () => void;
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  guildId,
  onLogout,
  isOpenMobile = false,
  onCloseMobile,
}) => {
  const [youtubeOpen, setYoutubeOpen] = useState(true);
  const [moderatorOpen, setModeratorOpen] = useState(true);

  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const currentTab = searchParams.get('tab') || 'channels';
  const isYouTube = location.pathname === '/youtube';

  const isChannelsActive = isYouTube && currentTab === 'channels';
  const isNotificationsActive = isYouTube && currentTab === 'notifications';
  const isSettingsActive = isYouTube && currentTab === 'settings';

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-xs font-semibold transition-all ${
      isActive
        ? 'bg-[#5865F2] text-white shadow-lg shadow-[#5865F2]/20'
        : 'text-gray-400 hover:text-white hover:bg-gray-800/60'
    }`;

  const subNavLinkClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
      isActive
        ? 'bg-[#5865F2]/15 text-[#858eff] font-semibold border-l-2 border-[#5865F2]'
        : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800/40'
    }`;

  const content = (
    <div className="flex flex-col h-full bg-[#151921] border-r border-gray-800 w-64 select-none">
      {/* Brand Header */}
      <div className="p-5 border-b border-gray-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#5865F2] flex items-center justify-center font-black text-white text-base shadow-md">
            PB
          </div>
          <div>
            <h1 className="font-extrabold text-white text-base tracking-wider leading-none">
              PB HERO
            </h1>
            <span className="text-[10px] text-gray-400 font-semibold tracking-wide">
              PERSONAL BOT
            </span>
          </div>
        </div>
      </div>

      {/* Navigation items */}
      <nav className="flex-1 overflow-y-auto p-3.5 space-y-1.5 custom-scrollbar">
        {/* Overview */}
        <NavLink to="/" end className={navLinkClass} onClick={onCloseMobile}>
          <LayoutDashboard className="w-4 h-4" />
          <span>Overview</span>
        </NavLink>

        {/* YouTube Section */}
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setYoutubeOpen(!youtubeOpen)}
            className="flex items-center justify-between w-full px-3.5 py-2 text-xs font-bold text-gray-400 hover:text-white rounded-lg transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <Youtube className="w-4 h-4 text-red-500" />
              <span className="uppercase tracking-wider">YouTube</span>
            </div>
            {youtubeOpen ? (
              <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
            )}
          </button>

          {youtubeOpen && (
            <div className="space-y-0.5 pl-5 mt-1 border-l border-gray-800 ml-4">
              <Link
                to="/youtube?tab=channels"
                className={subNavLinkClass({ isActive: isChannelsActive })}
                onClick={onCloseMobile}
              >
                <ListTree className="w-3.5 h-3.5" />
                <span>Channels</span>
              </Link>
              <Link
                to="/youtube?tab=notifications"
                className={subNavLinkClass({ isActive: isNotificationsActive })}
                onClick={onCloseMobile}
              >
                <Bell className="w-3.5 h-3.5" />
                <span>Notifications</span>
              </Link>
              <Link
                to="/youtube?tab=settings"
                className={subNavLinkClass({ isActive: isSettingsActive })}
                onClick={onCloseMobile}
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Settings</span>
              </Link>
            </div>
          )}
        </div>

        {/* Moderator Section */}
        <div className="pt-2">
          <button
            type="button"
            onClick={() => setModeratorOpen(!moderatorOpen)}
            className="flex items-center justify-between w-full px-3.5 py-2 text-xs font-bold text-gray-400 hover:text-white rounded-lg transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <Shield className="w-4 h-4 text-[#5865F2]" />
              <span className="uppercase tracking-wider">Moderator</span>
            </div>
            {moderatorOpen ? (
              <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-gray-500" />
            )}
          </button>

          {moderatorOpen && (
            <div className="space-y-0.5 pl-5 mt-1 border-l border-gray-800 ml-4">
              <NavLink to="/moderator" end className={subNavLinkClass} onClick={onCloseMobile}>
                <LayoutDashboard className="w-3.5 h-3.5" />
                <span>Overview</span>
              </NavLink>
              <NavLink to="/moderator/policies" className={subNavLinkClass} onClick={onCloseMobile}>
                <FileText className="w-3.5 h-3.5" />
                <span>Channel Policies</span>
              </NavLink>
              <NavLink to="/moderator/profiles" className={subNavLinkClass} onClick={onCloseMobile}>
                <Bookmark className="w-3.5 h-3.5" />
                <span>Policy Profiles</span>
              </NavLink>
              <NavLink to="/moderator/exemptions" className={subNavLinkClass} onClick={onCloseMobile}>
                <ShieldAlert className="w-3.5 h-3.5" />
                <span>Exemptions & Bypass</span>
              </NavLink>
              <NavLink to="/moderator/automod" className={subNavLinkClass} onClick={onCloseMobile}>
                <Zap className="w-3.5 h-3.5" />
                <span>Automod Rules</span>
              </NavLink>
              <NavLink to="/moderator/warnings" className={subNavLinkClass} onClick={onCloseMobile}>
                <AlertTriangle className="w-3.5 h-3.5" />
                <span>Warnings & Actions</span>
              </NavLink>
              <NavLink to="/moderator/greetings" className={subNavLinkClass} onClick={onCloseMobile}>
                <UserPlus className="w-3.5 h-3.5" />
                <span>Welcome & Goodbye</span>
              </NavLink>
              <NavLink to="/moderator/logs" className={subNavLinkClass} onClick={onCloseMobile}>
                <ScrollText className="w-3.5 h-3.5" />
                <span>Moderation Logs</span>
              </NavLink>
              <NavLink to="/moderator/settings" className={subNavLinkClass} onClick={onCloseMobile}>
                <Sliders className="w-3.5 h-3.5" />
                <span>Settings</span>
              </NavLink>
            </div>
          )}
        </div>

        {/* Channels */}
        <div className="pt-2">
          <NavLink to="/channels" className={navLinkClass} onClick={onCloseMobile}>
            <Hash className="w-4 h-4" />
            <span>Channels</span>
          </NavLink>
        </div>

        {/* Security */}
        <NavLink to="/security" className={navLinkClass} onClick={onCloseMobile}>
          <Lock className="w-4 h-4" />
          <span>Security</span>
        </NavLink>

        {/* System */}
        <NavLink to="/system" className={navLinkClass} onClick={onCloseMobile}>
          <Cpu className="w-4 h-4" />
          <span>System</span>
        </NavLink>
      </nav>

      {/* Connected Server Badge (Single-Server Enforcement) */}
      <div className="p-3.5 border-t border-gray-800 bg-[#12161f]">
        <div className="bg-[#0B0E14] border border-gray-800/80 rounded-xl p-3 space-y-1">
          <div className="flex items-center gap-1.5 text-gray-400 text-[10px] font-bold uppercase tracking-wider">
            <Server className="w-3 h-3 text-emerald-400" />
            <span>Connected Server</span>
          </div>
          <span className="text-xs font-bold text-white block truncate">PB HERO SERVER</span>
          {guildId && (
            <span className="text-[10px] text-gray-500 font-mono block truncate">
              ID: {guildId}
            </span>
          )}
        </div>

        <button
          onClick={onLogout}
          className="mt-3 flex items-center justify-center gap-2 w-full py-2 px-3 text-xs font-semibold text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-xl transition-colors border border-transparent hover:border-rose-500/20"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Sign Out</span>
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex h-full shrink-0">{content}</aside>

      {/* Mobile drawer overlay */}
      {isOpenMobile && (
        <div className="fixed inset-0 z-40 md:hidden flex">
          <div
            className="fixed inset-0 bg-black/70 backdrop-blur-sm"
            onClick={onCloseMobile}
          />
          <div className="relative z-50 animate-slide-right h-full">{content}</div>
        </div>
      )}
    </>
  );
};
