import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import DashboardLayout from './layouts/DashboardLayout';
import Overview from './pages/Overview';
import YouTube from './pages/YouTube';
import Moderation from './pages/Moderation';
import Monitor from './pages/Monitor';
import Permissions from './pages/Permissions';
import Settings from './pages/Settings';
import Logs from './pages/Logs';

function App() {
  return (
    // Main routing setup for the Dashboard Phase-1
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Overview />} />
          <Route path="youtube" element={<YouTube />} />
          <Route path="moderation" element={<Moderation />} />
          <Route path="monitor" element={<Monitor />} />
          <Route path="permissions" element={<Permissions />} />
          <Route path="settings" element={<Settings />} />
          <Route path="logs" element={<Logs />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
