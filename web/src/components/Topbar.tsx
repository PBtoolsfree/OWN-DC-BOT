import React from 'react';
import { SystemStatus } from '../types';
import { LogOut, Wifi, Activity, Menu, Shield } from 'lucide-react';

interface TopbarProps {
  status: SystemStatus | null;
  username: string;
  onLogout: () => void;
  onToggleSidebar?: () => void;
}

export const Topbar: React.FC<TopbarProps> = ({
  status,
  username,
  onLogout,
  onToggleSidebar,
}) => {
  const isOnline = status?.bot?.connected ?? false;
  const latency = status?.bot?.latency_ms ?? 0;
  const guildName = status?.bot?.guild_name || 'PB HERO SERVER';

  return (
    <header className="h-16 bg-[#151921] border-b border-gray-800 px-6 flex items-center justify-between shadow-md select-none shrink-0 z-20">
      {/* Left: Mobile hamburger & Brand */}
      <div className="flex items-center gap-3">
        {onToggleSidebar && (
          <button
            type="button"
            onClick={onToggleSidebar}
            className="md:hidden p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
            aria-label="Toggle Navigation"
          >
            <Menu className="w-5 h-5" />
          </button>
        )}

        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-[#5865F2] flex items-center justify-center text-white font-bold text-xs shadow-md">
            PB
          </div>
          <div>
            <h2 className="text-sm font-bold text-white tracking-wide leading-none">
              PB HERO PERSONAL BOT
            </h2>
            <span className="text-[10px] text-gray-400 font-medium">
              Private Server Control Panel • {guildName}
            </span>
          </div>
        </div>
      </div>

      {/* Right: Live Status Indicators & Admin Session */}
      <div className="flex items-center gap-4 text-xs">
        {/* Status indicator */}
        <div className="hidden sm:flex items-center gap-2 bg-[#0B0E14] border border-gray-800 px-3 py-1.5 rounded-full">
          <span
            className={`w-2 h-2 rounded-full ${
              isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'
            }`}
          />
          <span className="text-gray-400 text-[11px] font-semibold">BOT:</span>
          <span
            className={`font-bold tracking-wider text-[11px] ${
              isOnline ? 'text-emerald-400' : 'text-rose-400'
            }`}
          >
            {isOnline ? 'ONLINE' : 'OFFLINE'}
          </span>
        </div>

        {/* Discord connection indicator */}
        <div className="hidden md:flex items-center gap-1.5 text-gray-400 bg-[#0B0E14] border border-gray-800 px-3 py-1.5 rounded-full">
          <Wifi className="w-3.5 h-3.5 text-[#5865F2]" />
          <span className="text-gray-400 text-[11px] font-semibold">DISCORD:</span>
          <span className="text-gray-200 font-semibold text-[11px]">
            {isOnline ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>

        {/* Latency */}
        <div className="hidden lg:flex items-center gap-1.5 text-gray-400 bg-[#0B0E14] border border-gray-800 px-3 py-1.5 rounded-full">
          <Activity className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-gray-400 text-[11px] font-semibold">LATENCY:</span>
          <span className="text-gray-200 font-mono font-semibold text-[11px]">{latency} ms</span>
        </div>

        {/* User Badge */}
        <div className="flex items-center gap-2 pl-2 border-l border-gray-800">
          <div className="w-7 h-7 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-300">
            <Shield className="w-3.5 h-3.5 text-[#5865F2]" />
          </div>
          <div className="hidden sm:block text-left">
            <span className="text-[10px] text-gray-500 block uppercase font-bold tracking-wider">
              USER
            </span>
            <span className="text-xs font-bold text-white block uppercase tracking-wide">
              {username || 'ADMIN'}
            </span>
          </div>
        </div>

        {/* Logout Button */}
        <button
          onClick={onLogout}
          title="Sign out"
          className="flex items-center gap-1.5 px-3 py-1.5 text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors border border-transparent hover:border-rose-500/20"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span className="hidden sm:inline font-medium">Logout</span>
        </button>
      </div>
    </header>
  );
};
