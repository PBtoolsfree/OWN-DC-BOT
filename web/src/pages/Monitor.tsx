import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Activity, Server, Youtube, Cpu, Clock, CheckCircle, AlertTriangle } from 'lucide-react';

export default function Monitor() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const result = await api.get('/monitor');
      setData(result);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to load monitor data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-gray-400">Loading monitor...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2"><Activity className="text-blue-500" /> Server Monitor</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        <div className="bg-[#151921] border border-gray-800 rounded-lg p-6">
          <h3 className="text-gray-400 font-medium mb-4 flex items-center gap-2"><Server size={18} /> System Core</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">Discord Gateway</span>
              <span className={`font-medium ${data.discordGateway === 'Connected' ? 'text-green-500' : 'text-red-500'}`}>{data.discordGateway}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Bot Service</span>
              <span className={`font-medium ${data.botStatus === 'Running' ? 'text-green-500' : 'text-red-500'}`}>{data.botStatus}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Dashboard API</span>
              <span className="font-medium text-green-500">{data.dashboardApi}</span>
            </div>
          </div>
        </div>

        <div className="bg-[#151921] border border-gray-800 rounded-lg p-6">
          <h3 className="text-gray-400 font-medium mb-4 flex items-center gap-2"><Cpu size={18} /> Hardware Resources</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">CPU Load (1m)</span>
              <span className="font-medium">{data.cpu.toFixed(2)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Memory Used</span>
              <span className="font-medium">{(data.memory / 1024 / 1024).toFixed(2)} MB</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">System Uptime</span>
              <span className="font-medium flex items-center gap-1"><Clock size={14} /> {Math.floor(data.uptime / 3600)}h {Math.floor((data.uptime % 3600) / 60)}m</span>
            </div>
          </div>
        </div>

        <div className="bg-[#151921] border border-gray-800 rounded-lg p-6">
          <h3 className="text-gray-400 font-medium mb-4 flex items-center gap-2"><Youtube size={18} /> YouTube Worker</h3>
          <div className="space-y-3">
            <div className="flex justify-between">
              <span className="text-gray-400">Worker Status</span>
              <span className={`font-medium ${data.youtubeMonitor === 'Active' ? 'text-green-500' : 'text-red-500'}`}>{data.youtubeMonitor}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Tracked Channels</span>
              <span className="font-medium">{data.youtubeHealth.total} ({data.youtubeHealth.enabled} enabled)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Health</span>
              <span className="font-medium text-green-500 flex items-center gap-1">
                {data.youtubeHealth.warning > 0 ? <AlertTriangle size={14} className="text-yellow-500"/> : <CheckCircle size={14} />} 
                {data.youtubeHealth.healthy} Healthy
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
