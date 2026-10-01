import { useEffect, useState } from 'react';
import { Outlet, Link, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import { LayoutDashboard, Youtube, Shield, Settings, Activity, Key, ScrollText, LogOut } from 'lucide-react';

export default function DashboardLayout() {
  const [loading, setLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    api.get('/auth/me')
      .then(() => setLoading(false))
      .catch(() => {
        window.location.href = '/login';
      });
  }, []);

  const handleLogout = async () => {
    await api.post('/auth/logout', {});
    window.location.href = '/login';
  };

  if (loading) {
    return <div className="min-h-screen bg-[#0B0E14] flex items-center justify-center text-white">Verifying session...</div>;
  }

  const navItems = [
    { name: 'Overview', path: '/', icon: LayoutDashboard },
    { name: 'YouTube', path: '/youtube', icon: Youtube },
    { name: 'Moderation', path: '/moderation', icon: Shield },
    { name: 'Server Monitor', path: '/monitor', icon: Activity },
    { name: 'Permissions', path: '/permissions', icon: Key },
    { name: 'Settings', path: '/settings', icon: Settings },
    { name: 'Logs', path: '/logs', icon: ScrollText },
  ];

  return (
    <div className="flex h-screen bg-[#0B0E14] text-white">
      {/* Sidebar */}
      <div className="w-64 bg-[#151921] border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-xl font-bold">PB HERO Bot</h1>
        </div>
        
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={\`flex items-center space-x-3 px-4 py-3 rounded transition-colors \${
                  isActive ? 'bg-[#5865F2] text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                }\`}
              >
                <Icon size={20} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-gray-800">
          <button 
            onClick={handleLogout}
            className="flex items-center space-x-3 px-4 py-3 w-full rounded text-gray-400 hover:bg-red-500/10 hover:text-red-500 transition-colors"
          >
            <LogOut size={20} />
            <span>Logout</span>
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
