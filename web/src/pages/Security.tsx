import { useState, useEffect, type FormEvent } from 'react';
import { securityApi } from '../api/security';
import { authApi } from '../api/auth';
import { validatePasswordStrength } from '../utils/validation';
import { StatusBadge } from '../components/StatusBadge';
import { toast } from '../hooks/useToast';
import { Lock, User, KeyRound, Loader2, ShieldCheck } from 'lucide-react';

export default function Security() {
  const [username, setUsername] = useState('ADMIN');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [validationError, setValidationError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    authApi
      .getMe()
      .then((user) => {
        if (user) setUsername(user.username);
      })
      .catch(() => {});
  }, []);

  const handleChangePassword = async (e: FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    if (!currentPassword) {
      setValidationError('Current password is required.');
      return;
    }

    const check = validatePasswordStrength(newPassword);
    if (!check.valid) {
      setValidationError(check.error || 'Password is too weak.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setValidationError('New password and confirmation do not match.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await securityApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      if (res.success) {
        toast.success(res.message || 'Password changed successfully!');
        setCurrentPassword('');
        setNewPassword('');
        setConfirmPassword('');
      }
    } catch (err: any) {
      setValidationError(err.message || 'Failed to update password.');
      toast.error(err.message || 'Password update failed.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-4xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <Lock className="w-7 h-7 text-[#5865F2]" />
          <span>Security & Access Control</span>
        </h1>
        <p className="text-xs text-gray-400 mt-1">
          Manage private dashboard credentials, session isolation, and brute-force protection.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
        {/* Account & Session Status Card */}
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-5">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3 flex items-center gap-2">
            <User className="w-4 h-4 text-[#5865F2]" />
            <span>Dashboard Administrator Account</span>
          </h2>

          <div className="space-y-3 text-xs">
            <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
              <span className="text-gray-400">Username</span>
              <span className="font-bold text-white font-mono">{username}</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
              <span className="text-gray-400">Session Status</span>
              <StatusBadge status="online" label="ACTIVE • VALID 24H" />
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
              <span className="text-gray-400">Password Hashing</span>
              <span className="font-medium text-emerald-400 font-mono">Argon2id (RFC 9106)</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-xl bg-[#0B0E14] border border-gray-800">
              <span className="text-gray-400">Session Cookie Security</span>
              <span className="font-medium text-indigo-400 font-mono">HttpOnly • SameSite=Lax</span>
            </div>
          </div>

          <div className="bg-[#0B0E14] border border-gray-800 rounded-xl p-4 space-y-2">
            <span className="text-xs font-bold text-gray-300 block uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Login Security Defenses</span>
            </span>
            <ul className="text-xs text-gray-400 space-y-1 list-disc list-inside">
              <li>In-memory brute-force rate limiter</li>
              <li>Single fixed Discord server isolation</li>
              <li>Bot token isolated from browser memory</li>
            </ul>
          </div>
        </div>

        {/* Change Password Card */}
        <div className="bg-[#151921] border border-gray-800 rounded-2xl p-6 shadow-xl space-y-5">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider border-b border-gray-800 pb-3 flex items-center gap-2">
            <KeyRound className="w-4 h-4 text-[#5865F2]" />
            <span>Change Administrator Password</span>
          </h2>

          <form onSubmit={handleChangePassword} className="space-y-4">
            {validationError && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs text-rose-300">
                {validationError}
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">Current Password</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                disabled={submitting}
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">New Password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Minimum 8 characters"
                disabled={submitting}
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-gray-300 block">
                Confirm New Password
              </label>
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Repeat new password"
                disabled={submitting}
                className="w-full bg-[#0B0E14] border border-gray-700 rounded-xl px-3.5 py-2 text-xs text-white focus:outline-none focus:border-[#5865F2]"
              />
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={submitting}
                className="w-full py-2.5 px-4 bg-[#5865F2] hover:bg-[#4752c4] text-white rounded-xl text-xs font-bold transition-all shadow-lg shadow-[#5865F2]/20 flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {submitting ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Updating Password...</span>
                  </>
                ) : (
                  <span>Update Password</span>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
