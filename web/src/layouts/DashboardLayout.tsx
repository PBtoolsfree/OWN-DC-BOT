import { useEffect, useState, useCallback } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from '../components/Sidebar';
import { Topbar } from '../components/Topbar';
import { ToastContainer } from '../components/Toast';
import { authApi } from '../api/auth';
import { systemApi } from '../api/system';
import { SystemStatus } from '../types';
import { toast } from '../hooks/useToast';
import { Loader2 } from 'lucide-react';

export default function DashboardLayout() {
  const [loading, setLoading] = useState(true);
  const [username, setUsername] = useState('ADMIN');
  const [guildId, setGuildId] = useState<string>('');
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [sidebarOpenMobile, setSidebarOpenMobile] = useState(false);
  const navigate = useNavigate();

  // Fetch live system status
  const fetchStatus = useCallback(async () => {
    try {
      const data = await systemApi.getStatus();
      setStatus(data);
    } catch (_) {
      // Ignored for polling
    }
  }, []);

  // Initial session verification
  useEffect(() => {
    let isMounted = true;

    authApi
      .getMe()
      .then((user) => {
        if (!isMounted) return;
        if (user && user.authenticated) {
          setUsername(user.username);
          setGuildId(user.guild_id);
          setLoading(false);
          // Initial status fetch
          fetchStatus();
        } else {
          navigate('/login');
        }
      })
      .catch(() => {
        if (isMounted) navigate('/login');
      });

    return () => {
      isMounted = false;
    };
  }, [navigate, fetchStatus]);

  // Periodic status poll (20s)
  useEffect(() => {
    if (loading) return;

    const interval = setInterval(() => {
      fetchStatus();
    }, 20000);

    return () => clearInterval(interval);
  }, [loading, fetchStatus]);

  const handleLogout = async () => {
    try {
      await authApi.logout();
      toast.info('You have logged out.');
      navigate('/login');
    } catch (_) {
      navigate('/login');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0B0E14] flex flex-col items-center justify-center text-white space-y-4">
        <div className="w-12 h-12 rounded-2xl bg-[#5865F2] flex items-center justify-center font-black text-xl shadow-xl animate-pulse">
          PB
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400 font-medium">
          <Loader2 className="w-4 h-4 animate-spin text-[#5865F2]" />
          <span>Verifying private bot session...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-[#0B0E14] text-white overflow-hidden font-sans">
      <ToastContainer />

      {/* Main Sidebar */}
      <Sidebar
        guildId={guildId}
        onLogout={handleLogout}
        isOpenMobile={sidebarOpenMobile}
        onCloseMobile={() => setSidebarOpenMobile(false)}
      />

      {/* Main App Canvas */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <Topbar
          status={status}
          username={username}
          onLogout={handleLogout}
          onToggleSidebar={() => setSidebarOpenMobile(!sidebarOpenMobile)}
        />

        {/* Dynamic Page Content */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-[#0B0E14] custom-scrollbar">
          <div className="max-w-7xl mx-auto space-y-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
