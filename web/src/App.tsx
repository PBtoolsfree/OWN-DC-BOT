import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import DashboardLayout from './layouts/DashboardLayout';
import Overview from './pages/Overview';
import YouTube from './pages/YouTube';
import YouTubeChannelDetails from './pages/YouTubeChannel';
import Moderator from './pages/Moderator';
import ChannelPolicies from './pages/ChannelPolicies';
import PolicyProfiles from './pages/PolicyProfiles';
import ModerationLogs from './pages/ModerationLogs';
import Channels from './pages/Channels';
import Security from './pages/Security';
import System from './pages/System';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<DashboardLayout />}>
          <Route index element={<Overview />} />
          <Route path="youtube" element={<YouTube />} />
          <Route path="youtube/channels" element={<YouTube />} />
          <Route path="youtube/notifications" element={<YouTube />} />
          <Route path="youtube/settings" element={<YouTube />} />
          <Route path="youtube/:id" element={<YouTubeChannelDetails />} />
          <Route path="moderator" element={<Moderator />} />
          <Route path="moderator/policies" element={<ChannelPolicies />} />
          <Route path="moderator/policies/:channelId" element={<ChannelPolicies />} />
          <Route path="moderator/profiles" element={<PolicyProfiles />} />
          <Route path="moderator/logs" element={<ModerationLogs />} />
          <Route path="moderator/settings" element={<Moderator />} />
          <Route path="channels" element={<Channels />} />
          <Route path="security" element={<Security />} />
          <Route path="system" element={<System />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
