import { useState, useEffect, type FormEvent } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import { ToastContainer } from '../components/Toast';
import { toast } from '../hooks/useToast';
import { Shield, Lock, User, Loader2, AlertCircle } from 'lucide-react';

interface LoginProps {
  onLoginSuccess?: () => void;
}

export function Login({ onLoginSuccess }: LoginProps = {}) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    // Check if session expired
    if (searchParams.get('error') === 'session_expired') {
      setErrorMessage('Your session has expired. Please log in again.');
    } else if (searchParams.get('error') === 'forbidden') {
      setErrorMessage('Access denied. Administrator privileges required.');
    }

    // Check if already authenticated
    authApi
      .getMe()
      .then((res) => {
        if (res && res.authenticated) {
          navigate('/');
        }
      })
      .catch(() => {});
  }, [searchParams, navigate]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!username.trim() || !password) {
      setErrorMessage('Please enter both username and password.');
      return;
    }

    setLoading(true);
    try {
      const res = await authApi.login({
        username: username.trim(),
        password,
      });

      if (res.success || (res as any).authenticated) {
        toast.success(`Welcome back, ${res.username || 'Admin'}!`);
        if (onLoginSuccess) {
          onLoginSuccess();
        }
        navigate('/');
      }
    } catch (err: any) {
      const status = err?.status || err?.response?.status;
      const detail = err?.data?.detail || err?.response?.data?.detail || err?.message;
      if (status === 401) {
        setErrorMessage('Invalid username or password.');
      } else if (status === 429) {
        setErrorMessage(detail || 'Too many login attempts. Please wait before trying again.');
      } else if (status === 403) {
        setErrorMessage('Access denied from this IP address.');
      } else {
        setErrorMessage(detail || 'Login failed. Please check your connection.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0B0E14] flex flex-col justify-center items-center px-4 font-sans select-none relative overflow-hidden">
      <ToastContainer />

      {/* Subtle background glow */}
      <div className="absolute w-[500px] h-[500px] rounded-full bg-[#5865F2]/5 blur-3xl pointer-events-none -top-32 -left-32" />
      <div className="absolute w-[400px] h-[400px] rounded-full bg-emerald-500/5 blur-3xl pointer-events-none -bottom-32 -right-32" />

      <div className="max-w-md w-full bg-[#151921] border border-gray-800 rounded-3xl p-8 shadow-2xl relative z-10 space-y-6">
        {/* Brand header */}
        <div className="text-center space-y-2">
          <div className="w-14 h-14 rounded-2xl bg-[#5865F2] flex items-center justify-center font-black text-white text-xl mx-auto shadow-lg shadow-[#5865F2]/30 mb-4">
            PB
          </div>
          <h1 className="text-xl font-extrabold text-white tracking-wide">
            PB HERO PERSONAL BOT
          </h1>
          <p className="text-xs text-gray-400 font-medium">
            Private Server Administration Control Panel
          </p>
        </div>

        {/* Error message card */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 flex items-start gap-2.5 text-xs text-rose-300 animate-fade-in">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400 mt-0.5" />
            <span className="leading-relaxed">{errorMessage}</span>
          </div>
        )}

        {/* Login form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="username" className="text-xs font-semibold text-gray-300 block">
              Username
            </label>
            <div className="relative">
              <User className="w-4 h-4 text-gray-500 absolute left-3.5 top-3" />
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Admin username"
                disabled={loading}
                autoComplete="username"
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] transition-colors"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="text-xs font-semibold text-gray-300 block">
              Password
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 text-gray-500 absolute left-3.5 top-3" />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                disabled={loading}
                autoComplete="current-password"
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl pl-10 pr-4 py-2.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#5865F2] transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-3 px-4 rounded-xl text-xs font-bold uppercase tracking-wider text-white bg-[#5865F2] hover:bg-[#4752c4] active:bg-[#3c45a5] transition-all shadow-lg shadow-[#5865F2]/20 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Authenticating...</span>
              </>
            ) : (
              <span>LOGIN</span>
            )}
          </button>
        </form>

        <div className="pt-4 border-t border-gray-800 text-center">
          <div className="inline-flex items-center gap-1.5 text-[11px] text-gray-500">
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span>Encrypted Session • Single-Server Authorized Access</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Login;
