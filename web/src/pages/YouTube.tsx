import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Youtube, Plus, Edit2, Trash2, Check, X, Bell } from 'lucide-react';

export default function YouTube() {
  const [channels, setChannels] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [formData, setFormData] = useState({
    id: '',
    discord_channel_id: '',
    channel_name: '',
    mention_role_id: '',
    custom_message: '',
    enabled: 1,
    channel_url: ''
  });

  useEffect(() => {
    fetchChannels();
  }, []);

  const fetchChannels = async () => {
    try {
      const data = await api.get('/youtube/channels');
      setChannels(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load channels');
    } finally {
      setLoading(false);
    }
  };

  const handleUrlChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setUrlInput(val);
    
    // Attempt to resolve UC... ID
    const match = val.match(/(?:channel\/|UC)([a-zA-Z0-9_-]{22})/);
    if (match) {
      const id = match[1].startsWith('UC') ? match[1] : \`UC\${match[1]}\`;
      setFormData({ ...formData, id, channel_url: \`https://youtube.com/channel/\${id}\` });
    } else {
      setFormData({ ...formData, id: '', channel_url: val });
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.id) {
      alert('Could not resolve YouTube Channel ID. Please provide a direct channel ID or URL containing UC...');
      return;
    }
    
    try {
      if (channels.find(c => c.id === formData.id)) {
        await api.patch(\`/youtube/channels/\${formData.id}\`, formData);
      } else {
        await api.post('/youtube/channels', formData);
      }
      setIsModalOpen(false);
      fetchChannels();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this channel?')) return;
    try {
      await api.delete(\`/youtube/channels/\${id}\`);
      fetchChannels();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleToggle = async (id: string, enabled: number) => {
    try {
      await api.patch(\`/youtube/channels/\${id}\`, { enabled: enabled === 1 ? 0 : 1 });
      fetchChannels();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleTest = async (id: string) => {
    try {
      await api.post(\`/youtube/channels/\${id}/test\`, {});
      alert('Test notification sent successfully!');
    } catch (err: any) {
      alert(err.message);
    }
  };

  if (loading) return <div className="text-gray-400">Loading channels...</div>;
  if (error) return <div className="text-red-500">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold flex items-center gap-2"><Youtube className="text-red-500" /> YouTube Channels</h2>
        <button onClick={() => {
          setUrlInput('');
          setFormData({ id: '', discord_channel_id: '', channel_name: '', mention_role_id: '', custom_message: '', enabled: 1, channel_url: '' });
          setIsModalOpen(true);
        }} className="flex items-center gap-2 bg-[#5865F2] hover:bg-[#4752C4] px-4 py-2 rounded transition-colors text-sm font-medium">
          <Plus size={16} /> Add Channel
        </button>
      </div>

      {channels.length === 0 ? (
        <div className="bg-[#151921] border border-gray-800 rounded-lg p-12 text-center">
          <Youtube className="mx-auto text-gray-600 mb-4" size={48} />
          <h3 className="text-xl font-bold text-gray-300">No YouTube channels configured.</h3>
        </div>
      ) : (
        <div className="bg-[#151921] border border-gray-800 rounded-lg overflow-hidden">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-gray-800/50 border-b border-gray-800 text-sm font-medium text-gray-400">
                <th className="p-4">Channel Name</th>
                <th className="p-4">YouTube ID</th>
                <th className="p-4">Discord Channel</th>
                <th className="p-4">Status</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800 text-sm">
              {channels.map((c) => (
                <tr key={c.id} className="hover:bg-gray-800/20 transition-colors">
                  <td className="p-4 font-medium"><a href={c.channel_url} target="_blank" className="hover:underline">{c.channel_name}</a></td>
                  <td className="p-4 text-gray-400 font-mono text-xs">{c.id}</td>
                  <td className="p-4 text-gray-400 font-mono text-xs">{c.discord_channel_id}</td>
                  <td className="p-4">
                    <button onClick={() => handleToggle(c.id, c.enabled)} className={\`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium \${c.enabled ? 'bg-green-500/10 text-green-500' : 'bg-red-500/10 text-red-500'}\`}>
                      {c.enabled ? <><Check size={12}/> Enabled</> : <><X size={12}/> Disabled</>}
                    </button>
                  </td>
                  <td className="p-4 text-right space-x-2">
                    <button onClick={() => handleTest(c.id)} className="p-2 text-blue-400 hover:text-white bg-blue-500/10 rounded transition-colors" title="Test Notification">
                      <Bell size={16} />
                    </button>
                    <button onClick={() => { 
                      setFormData(c); 
                      setUrlInput(c.channel_url || c.id);
                      setIsModalOpen(true); 
                    }} className="p-2 text-gray-400 hover:text-white bg-gray-800 rounded transition-colors" title="Edit">
                      <Edit2 size={16} />
                    </button>
                    <button onClick={() => handleDelete(c.id)} className="p-2 text-red-500 hover:text-red-400 bg-red-500/10 rounded transition-colors" title="Delete">
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
          <div className="bg-[#151921] rounded-lg shadow-xl w-full max-w-lg border border-gray-800">
            <div className="p-6 border-b border-gray-800 flex justify-between items-center">
              <h3 className="text-xl font-bold">{channels.find(c => c.id === formData.id) ? 'Edit Channel' : 'Add Channel'}</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-gray-400 hover:text-white"><X size={24} /></button>
            </div>
            <form onSubmit={handleSave} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">YouTube URL or Channel ID</label>
                <input required type="text" value={urlInput} onChange={handleUrlChange} disabled={!!channels.find(c => c.id === formData.id)} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white disabled:opacity-50" placeholder="https://youtube.com/channel/UC..." />
                {!formData.id && urlInput.length > 0 && (
                  <p className="text-xs text-red-400 mt-1">Could not resolve UC... ID. Please provide the exact ID.</p>
                )}
                {formData.id && (
                  <p className="text-xs text-green-400 mt-1">Resolved ID: {formData.id}</p>
                )}
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Display Name</label>
                <input required type="text" value={formData.channel_name} onChange={e => setFormData({...formData, channel_name: e.target.value})} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Discord Channel ID</label>
                <input required type="text" value={formData.discord_channel_id} onChange={e => setFormData({...formData, discord_channel_id: e.target.value})} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Role Mention ID (Optional)</label>
                <input type="text" value={formData.mention_role_id || ''} onChange={e => setFormData({...formData, mention_role_id: e.target.value})} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" placeholder="e.g. 1234567890" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-400 mb-1">Custom Message (Optional)</label>
                <input type="text" value={formData.custom_message || ''} onChange={e => setFormData({...formData, custom_message: e.target.value})} className="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" placeholder="Hey @role, new video!" />
              </div>
              
              <div className="flex justify-end gap-3 mt-6 pt-4 border-t border-gray-800">
                <button type="button" onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-gray-400 hover:text-white transition-colors">Cancel</button>
                <button type="submit" disabled={!formData.id} className="px-4 py-2 bg-[#5865F2] hover:bg-[#4752C4] text-white rounded transition-colors font-medium disabled:opacity-50">Save Channel</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
