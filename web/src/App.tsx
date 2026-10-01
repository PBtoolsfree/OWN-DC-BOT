import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

function DashboardLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-900 text-white">
      <div className="w-64 border-r border-gray-800 bg-gray-900 p-4">
        <h1 className="text-xl font-bold mb-8">PB HERO Bot</h1>
        <nav className="space-y-2">
          <a href="/" className="block p-2 rounded hover:bg-gray-800 text-gray-300">Overview</a>
          <a href="/youtube" className="block p-2 rounded hover:bg-gray-800 text-gray-300">YouTube</a>
          <a href="/moderation" className="block p-2 rounded hover:bg-gray-800 text-gray-300">Moderation</a>
          <a href="/settings" className="block p-2 rounded hover:bg-gray-800 text-gray-300">Settings</a>
        </nav>
      </div>
      <div className="flex-1 overflow-auto p-8">
        <h2 className="text-2xl font-semibold mb-4">Dashboard Overview</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-700">
            <h3 className="text-sm font-medium text-gray-400">Bot Status</h3>
            <p className="text-2xl font-bold text-green-400 mt-2">Online</p>
          </div>
          <div className="bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-700">
            <h3 className="text-sm font-medium text-gray-400">YouTube Channels</h3>
            <p className="text-2xl font-bold mt-2">Loading...</p>
          </div>
          <div className="bg-gray-800 p-6 rounded-lg shadow-sm border border-gray-700">
            <h3 className="text-sm font-medium text-gray-400">Moderation</h3>
            <p className="text-2xl font-bold text-green-400 mt-2">Active</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DashboardLayout />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
