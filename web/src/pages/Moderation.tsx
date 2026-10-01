import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Shield, Plus, Check, X, Trash2 } from 'lucide-react';

export default function Moderation() {
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({ rule_type: 'banned_words', config: '', enabled: 1, guild_id: '' });

  useEffect(() => {
    fetchRules();
  }, []);

  const fetchRules = async () => {
    try {
      const data = await api.get('/moderation/rules');
      setRules(data);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.post('/moderation/rules', formData);
      setIsModalOpen(false);
      fetchRules();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(\`/moderation/rules/\${id}\`);
      fetchRules();
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading) return <div className="text-gray-400">Loading moderation rules...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold flex items-center gap-2"><Shield className="text-green-500" /> Moderation Settings</h2>
        <button onClick={() => {
          setFormData({ rule_type: 'banned_words', config: '', enabled: 1, guild_id: '' });
          setIsModalOpen(true);
        }} className="flex items-center gap-2 bg-[#5865F2] hover:bg-[#4752C4] px-4 py-2 rounded transition-colors text-sm font-medium">
          <Plus size={16} /> Add Rule
        </button>
      </div>

      <div className="bg-[#151921] border border-gray-800 rounded-lg overflow-hidden">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="bg-gray-800/50 border-b border-gray-800 text-sm font-medium text-gray-400">
              <th className="p-4">Type</th>
              <th className="p-4">Guild ID</th>
              <th className="p-4">Config</th>
              <th className="p-4">Status</th>
              <th className="p-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800 text-sm">
            {rules.map((r) => (
              <tr key={r.id} className="hover:bg-gray-800/20 transition-colors">
                <td className="p-4 font-medium uppercase text-xs tracking-wider">{r.rule_type.replace('_', ' ')}</td>
                <td className="p-4 text-gray-400">{r.guild_id}</td>
                <td className="p-4 text-gray-400 font-mono text-xs max-w-xs truncate">{r.config}</td>
                <td className="p-4">
                  <span className={\`flex items-center w-fit gap-1 px-2 py-1 rounded-full text-xs font-medium \${r.enabled ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}\`}>
                    {r.enabled ? <><Check size={12}/> Enabled</> : <><X size={12}/> Disabled</>}
                  </span>
                </td>
                <td className="p-4 text-right">
                  <button onClick={() => handleDelete(r.id)} className="p-2 text-red-500 hover:text-red-400 bg-red-500/10 rounded transition-colors" title="Delete">
                    <Trash2 size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {rules.length === 0 && (
              <tr>
                <td colSpan={5} className="p-8 text-center text-gray-500">No moderation rules configured.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-[#151921] rounded-lg shadow-xl w-full max-w-lg border border-gray-800">
            <div className="p-6 border-b border-gray-800 flex justify-between items-center">
              <h3 className="text-xl font-bold">Add Moderation Rule</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-gray-400 hover:text-white"><X size={24} /></button>
            </div>
            <form onSubmit={handleSave} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Guild ID</label>
                <input required type="text" value={formData.guild_id} onChange={e => setFormData({...formData, guild_id: e.target.value})} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Rule Type</label>
                <select value={formData.rule_type} onChange={e => setFormData({...formData, rule_type: e.target.value})} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white">
                  <option value="banned_words">Banned Words</option>
                  <option value="anti_spam">Anti-Spam</option>
                  <option value="anti_links">Anti-Links</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Configuration (JSON / CSV)</label>
                <input required type="text" value={formData.config} onChange={e => setFormData({...formData, config: e.target.value})} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" placeholder="e.g. word1,word2 or {}" />
              </div>
              
              <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-800">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-gray-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" className="px-4 py-2 bg-[#5865F2] hover:bg-[#4752C4] text-white rounded transition-colors font-medium">Save Rule</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
