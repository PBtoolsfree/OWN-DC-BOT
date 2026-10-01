import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Key, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

export default function Permissions() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchPermissions();
  }, []);

  const fetchPermissions = async () => {
    try {
      const result = await api.get('/permissions');
      setData(result);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch permissions');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="text-gray-400">Loading permissions...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2"><Key className="text-purple-500" /> Server Permissions</h2>
      
      {data.missing && data.missing.length > 0 ? (
        <div className="bg-red-500/10 border border-red-500 rounded-lg p-6 mb-6">
          <h3 className="text-red-500 font-bold flex items-center gap-2 mb-2">
            <AlertTriangle size={20} /> Action Required
          </h3>
          <p className="text-red-400">The bot is missing permissions required for full functionality in the primary guild.</p>
        </div>
      ) : (
        <div className="bg-green-500/10 border border-green-500 rounded-lg p-6 mb-6 flex items-center gap-3">
          <CheckCircle className="text-green-500" size={24} />
          <div>
            <h3 className="text-green-500 font-bold">All Good</h3>
            <p className="text-green-400 text-sm">The bot has all required baseline permissions in the primary guild.</p>
          </div>
        </div>
      )}

      <div className="bg-[#151921] border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-800/50 border-b border-gray-800 text-sm font-medium text-gray-400">
              <th className="p-4">Discord Permission</th>
              <th className="p-4">Feature Segment</th>
              <th className="p-4">Reason</th>
              <th className="p-4">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800 text-sm">
            {['ViewChannel', 'SendMessages', 'EmbedLinks', 'ReadMessageHistory', 'ManageMessages', 'ModerateMembers'].map((permName) => {
              const isMissing = data.missing.find((m: any) => m.permission === permName);
              const segment = permName === 'ModerateMembers' ? 'Moderation (Timeouts)' : 'General Chat';
              const reason = 'Required for core bot functionality';

              return (
                <tr key={permName} className="hover:bg-gray-800/20 transition-colors">
                  <td className="p-4 font-mono text-gray-300">{permName}</td>
                  <td className="p-4 text-gray-400">{segment}</td>
                  <td className="p-4 text-gray-400">{reason}</td>
                  <td className="p-4">
                    {isMissing ? (
                      <span className="flex items-center gap-1 text-red-500 font-medium">
                        <XCircle size={16} /> Missing
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-green-500 font-medium">
                        <CheckCircle size={16} /> Available
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
