import React, { useState } from 'react';
import { GreetingRecentActivity } from '../../types';
import { History, CheckCircle, XCircle, Beaker, Filter } from 'lucide-react';

interface RecentActivityTableProps {
  activities: GreetingRecentActivity[];
}

export const RecentActivityTable: React.FC<RecentActivityTableProps> = ({ activities }) => {
  const [filterType, setFilterType] = useState<string>('all');

  const filtered = activities.filter((act) => {
    if (filterType === 'all') return true;
    if (filterType === 'test') return act.is_test;
    if (filterType === 'dm') return act.event_type.toLowerCase().includes('dm');
    if (filterType === 'role') return act.event_type.toLowerCase().includes('role');
    if (filterType === 'rules') return act.event_type.toLowerCase().includes('rules');
    if (filterType === 'invite') return act.event_type.toLowerCase().includes('invite');
    if (filterType === 'welcome') return act.event_type.toLowerCase().includes('welcome') && !act.event_type.toLowerCase().includes('dm');
    if (filterType === 'goodbye') return act.event_type.toLowerCase().includes('goodbye') && !act.event_type.toLowerCase().includes('dm');
    return true;
  });

  const getEventBadge = (type: string) => {
    const t = type.toUpperCase();
    if (t.includes('WELCOME_DM') || t === 'WELCOME_DM') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/80 text-emerald-300 border border-emerald-800">WELCOME DM</span>;
    }
    if (t.includes('GOODBYE_DM') || t === 'GOODBYE_DM') {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/80 text-amber-300 border border-amber-800">GOODBYE DM</span>;
    }
    if (t.includes('WELCOME')) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950/80 text-indigo-300 border border-indigo-800">WELCOME</span>;
    }
    if (t.includes('GOODBYE')) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950/80 text-rose-300 border border-rose-800">GOODBYE</span>;
    }
    if (t.includes('ROLE')) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-950/80 text-cyan-300 border border-cyan-800">AUTO ROLE</span>;
    }
    if (t.includes('RULES')) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-fuchsia-950/80 text-fuchsia-300 border border-fuchsia-800">RULES</span>;
    }
    if (t.includes('INVITE')) {
      return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-950/80 text-blue-300 border border-blue-800">INVITE</span>;
    }
    return <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-gray-800 text-gray-300 border border-gray-700">{t}</span>;
  };

  return (
    <div className="bg-gray-850 rounded-2xl border border-gray-800 shadow-xl overflow-hidden">
      <div className="p-6 border-b border-gray-800 flex flex-wrap items-center justify-between gap-4 bg-gray-900/60">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gray-800 rounded-xl border border-gray-700 text-gray-300">
            <History className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">Server Events & Greeting Activity</h2>
            <p className="text-xs text-gray-400">
              Live audit ring of recent onboarding actions, DMs, role updates, and invites.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Filter className="w-3.5 h-3.5 text-gray-400" />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-xl px-3 py-1.5 text-xs text-white focus:outline-none focus:border-indigo-500"
          >
            <option value="all">All Events</option>
            <option value="welcome">Public Welcome</option>
            <option value="goodbye">Public Goodbye</option>
            <option value="dm">Direct Messages (DMs)</option>
            <option value="role">Auto Roles</option>
            <option value="rules">Rules Delivery</option>
            <option value="invite">Permanent Invites</option>
            <option value="test">Test Runs Only</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-gray-800 bg-gray-900/30 text-gray-400">
              <th className="py-3 px-4 font-semibold">Timestamp</th>
              <th className="py-3 px-4 font-semibold">Event Type</th>
              <th className="py-3 px-4 font-semibold">Target Member</th>
              <th className="py-3 px-4 font-semibold">Destination</th>
              <th className="py-3 px-4 font-semibold">Delivery Status</th>
              <th className="py-3 px-4 font-semibold">Notes / Diagnostics</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-gray-500">
                  No recent greeting events recorded yet.
                </td>
              </tr>
            ) : (
              filtered.map((item) => (
                <tr key={item.id} className="hover:bg-gray-800/30 transition-colors">
                  <td className="py-3 px-4 text-gray-400 font-mono whitespace-nowrap">
                    {new Date(item.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap">
                    <div className="flex items-center gap-1.5">
                      {getEventBadge(item.event_type)}
                      {item.is_test && (
                        <span className="px-1.5 py-0.5 rounded text-[9px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-0.5">
                          <Beaker className="w-2.5 h-2.5" />
                          TEST
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4 text-white font-medium truncate max-w-[160px]">
                    {item.username}
                  </td>
                  <td className="py-3 px-4 text-gray-300 font-mono">
                    {item.channel_name ? (item.channel_name.startsWith('#') ? item.channel_name : `#${item.channel_name}`) : 'Direct Message'}
                  </td>
                  <td className="py-3 px-4 whitespace-nowrap">
                    {item.status === 'delivered' ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400 font-semibold">
                        <CheckCircle className="w-3.5 h-3.5" /> Delivered
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-rose-400 font-semibold">
                        <XCircle className="w-3.5 h-3.5" /> Delivery Failed
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-gray-400 truncate max-w-[220px]">
                    {item.error_message || '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
