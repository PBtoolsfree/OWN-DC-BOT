import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ScrollText, ChevronLeft, ChevronRight, Filter } from 'lucide-react';

export default function Logs() {
  const [logs, setLogs] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchLogs(page);
  }, [page]);

  const fetchLogs = async (p: number) => {
    setLoading(true);
    try {
      const data = await api.get(`/logs?page=${p}`);
      setLogs(data.logs);
      setTotal(data.total);
    } catch (err: any) {
      setError(err.message || 'Failed to load logs');
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / 50) || 1;

  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold flex items-center gap-2"><ScrollText className="text-blue-400" /> Audit Logs</h2>
        <div className="text-sm text-gray-400">Total Events: {total}</div>
      </div>

      <div className="bg-[#151921] border border-gray-800 rounded-lg overflow-hidden flex flex-col h-[700px]">
        <div className="flex-1 overflow-auto">
          <table className="w-full text-left border-collapse">
            <thead className="sticky top-0 bg-[#151921] z-10">
              <tr className="bg-gray-800/50 border-b border-gray-800 text-sm font-medium text-gray-400">
                <th className="p-4 w-48">Timestamp</th>
                <th className="p-4 w-32">Category</th>
                <th className="p-4 w-48">Action</th>
                <th className="p-4">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 text-sm">
              {loading && logs.length === 0 ? (
                <tr><td colSpan={4} className="p-8 text-center text-gray-500">Loading logs...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={4} className="p-8 text-center text-gray-500">No logs found.</td></tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-800/20 transition-colors">
                    <td className="p-4 text-gray-400 whitespace-nowrap">{new Date(log.created_at).toLocaleString()}</td>
                    <td className="p-4">
                      <span className="bg-gray-800 text-gray-300 px-2 py-1 rounded text-xs font-mono uppercase">
                        {log.category}
                      </span>
                    </td>
                    <td className="p-4 font-medium text-gray-300">{log.action}</td>
                    <td className="p-4 text-gray-500 font-mono text-xs break-all">
                      {log.details ? log.details : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        
        {/* Pagination */}
        <div className="bg-gray-900 border-t border-gray-800 p-4 flex items-center justify-between">
          <button 
            disabled={page === 1} 
            onClick={() => setPage(p => Math.max(1, p - 1))}
            className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded disabled:opacity-50 transition-colors"
          >
            <ChevronLeft size={16} /> Previous
          </button>
          <span className="text-gray-400 text-sm">Page {page} of {totalPages}</span>
          <button 
            disabled={page >= totalPages} 
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            className="flex items-center gap-1 px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 rounded disabled:opacity-50 transition-colors"
          >
            Next <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
