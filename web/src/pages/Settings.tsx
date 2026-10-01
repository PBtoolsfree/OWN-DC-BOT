import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Settings as SettingsIcon, Save } from 'lucide-react';

export default function Settings() {
  const [data, setData] = useState<any>(null);
  const [formData, setFormData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const result = await api.get('/settings');
      setData(result);
      setFormData({
        YOUTUBE_POLL_INTERVAL_SECONDS: result.YOUTUBE_POLL_INTERVAL_SECONDS,
        MODERATION_ENABLED: result.MODERATION_ENABLED,
        MODERATION_LOG_CHANNEL_ID: result.MODERATION_LOG_CHANNEL_ID
      });
    } catch (err: any) {
      setError(err.message || 'Failed to fetch settings');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSuccessMessage(null);
    setError(null);
    
    try {
      await api.patch('/settings', formData);
      setSuccessMessage('Settings updated successfully.');
      setTimeout(() => setSuccessMessage(null), 3000);
      fetchSettings();
    } catch (err: any) {
      setError(err.message || 'Failed to update settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !formData) return <div className="text-gray-400">Loading settings...</div>;

  return (
    <div className="space-y-6 max-w-3xl">
      <h2 className="text-2xl font-bold flex items-center gap-2"><SettingsIcon className="text-gray-400" /> Settings</h2>

      {error && <div className="bg-red-500/10 border border-red-500 text-red-500 rounded p-4">{error}</div>}
      {successMessage && <div className="bg-green-500/10 border border-green-500 text-green-500 rounded p-4">{successMessage}</div>}

      <form onSubmit={handleSave} className="space-y-6">
        <div className="bg-[#151921] border border-gray-800 rounded-lg p-6 space-y-6">
          <h3 className="text-lg font-bold border-b border-gray-800 pb-2">Bot Configuration</h3>
          
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">YouTube Polling Interval (Seconds)</label>
            <input 
              type="number" 
              min="30" max="3600"
              value={formData.YOUTUBE_POLL_INTERVAL_SECONDS} 
              onChange={e => setFormData({...formData, YOUTUBE_POLL_INTERVAL_SECONDS: parseInt(e.target.value, 10)})}
              className="w-full bg-gray-900 border border-gray-700 rounded p-3 text-white max-w-sm" 
            />
            <p className="text-xs text-gray-500 mt-1">Minimum 30 seconds. Restart may be required for poll loop to sync.</p>
          </div>

          <div className="flex items-center gap-3 pt-2">
            <input 
              type="checkbox" 
              id="mod_enabled"
              checked={formData.MODERATION_ENABLED} 
              onChange={e => setFormData({...formData, MODERATION_ENABLED: e.target.checked})}
              className="w-5 h-5 bg-gray-900 border-gray-700 rounded" 
            />
            <label htmlFor="mod_enabled" className="text-sm font-medium text-gray-200 cursor-pointer">Enable Global Moderation Filter</label>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-1">Moderation Log Channel ID (Optional)</label>
            <input 
              type="text" 
              value={formData.MODERATION_LOG_CHANNEL_ID} 
              onChange={e => setFormData({...formData, MODERATION_LOG_CHANNEL_ID: e.target.value})}
              className="w-full bg-gray-900 border border-gray-700 rounded p-3 text-white max-w-sm" 
              placeholder="e.g. 1234567890"
            />
          </div>
        </div>

        <div className="bg-[#151921] border border-gray-800 rounded-lg p-6 space-y-6">
          <h3 className="text-lg font-bold border-b border-gray-800 pb-2">Environment (Read-Only)</h3>
          
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Primary Guild ID</label>
            <input 
              type="text" 
              value={data.DISCORD_PRIMARY_GUILD_ID} 
              disabled
              className="w-full bg-gray-900/50 border border-gray-800 rounded p-3 text-gray-500 max-w-sm cursor-not-allowed" 
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-500 mb-1">Dashboard URL</label>
            <input 
              type="text" 
              value={data.DASHBOARD_URL} 
              disabled
              className="w-full bg-gray-900/50 border border-gray-800 rounded p-3 text-gray-500 max-w-sm cursor-not-allowed" 
            />
          </div>
        </div>

        <div className="flex justify-start">
          <button 
            type="submit" 
            disabled={saving}
            className="flex items-center gap-2 px-6 py-3 bg-[#5865F2] hover:bg-[#4752C4] text-white rounded font-medium transition-colors disabled:opacity-50"
          >
            <Save size={18} /> {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    </div>
  );
}
