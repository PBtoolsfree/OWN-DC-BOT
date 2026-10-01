import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Server, Activity, Database, Youtube, Bell, Shield, AlertTriangle } from 'lucide-react';

export default function Overview() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const result = await api.get('/overview');
      setData(result);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load overview data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-gray-400">Loading overview...</div>;
  if (error) return (
    <div className="bg-red-500/10 border border-red-500 text-red-500 p-4 rounded-lg flex justify-between items-center">
      <span>{error}</span>
      <button onClick={fetchData} className="px-4 py-2 bg-red-500/20 rounded hover:bg-red-500/30">Retry</button>
    </div>
  );
  if (!data) return <div className="text-gray-400">No data available.</div>;

  const cards = [
    { label: 'Bot Status', value: data.botStatus, icon: Server, color: data.botStatus === 'Online' ? 'text-green-500' : 'text-red-500' },
    { label: 'Gateway Ping', value: \`\${data.gatewayPing}ms\`, icon: Activity, color: 'text-blue-500' },
    { label: 'Uptime', value: \`\${Math.floor(data.uptime / 3600)}h \${Math.floor((data.uptime % 3600) / 60)}m\`, icon: Activity, color: 'text-purple-500' },
    { label: 'Database Status', value: data.databaseStatus, icon: Database, color: 'text-green-500' },
    { label: 'YouTube Channels', value: data.youtubeChannelsCount, icon: Youtube, color: 'text-red-500' },
    { label: 'Notifications Sent', value: data.youtubeNotificationsSent, icon: Bell, color: 'text-yellow-500' },
    { label: 'Moderation', value: data.moderationStatus, icon: Shield, color: data.moderationStatus === 'Active' ? 'text-green-500' : 'text-gray-500' },
    { label: 'Recent Errors', value: data.recentErrors, icon: AlertTriangle, color: data.recentErrors > 0 ? 'text-red-500' : 'text-gray-500' },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Dashboard Overview</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        {cards.map((card, i) => {
          const Icon = card.icon;
          return (
            <div key={i} className="bg-[#151921] border border-gray-800 rounded-lg p-6 shadow-xl flex items-start justify-between">
              <div>
                <h3 className="text-gray-400 text-sm font-medium">{card.label}</h3>
                <p className={\`text-2xl font-bold mt-2 \${card.color}\`}>{card.value}</p>
              </div>
              <div className="p-3 bg-gray-800/50 rounded-lg">
                <Icon className={card.color} size={24} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
