import React from 'react';
import { PolicyProfile, PolicyValue } from '../types';
import { Shield, Check, X, Minus, Copy, Trash2, ArrowRight, Edit3 } from 'lucide-react';

interface PolicyPresetCardProps {
  profile: PolicyProfile;
  onApply: (profile: PolicyProfile) => void;
  onClone?: (profile: PolicyProfile) => void;
  onEdit?: (profile: PolicyProfile) => void;
  onView?: (profile: PolicyProfile) => void;
  onDelete?: (id: number, name: string) => void;
}

export const PolicyPresetCard: React.FC<PolicyPresetCardProps> = ({
  profile,
  onApply,
  onClone,
  onEdit,
  onView,
  onDelete,
}) => {
  const isVoice = profile.policy_type === 'voice' || profile.name.startsWith('VOICE');

  const renderRuleBadge = (label: string, value?: PolicyValue) => {
    if (!value) return null;
    let color = 'bg-gray-800 text-gray-400 border-gray-700';
    let icon = <Minus className="w-3 h-3" />;

    if (value === 'allow') {
      color = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      icon = <Check className="w-3 h-3" />;
    } else if (value === 'deny') {
      color = 'bg-rose-500/10 text-rose-400 border-rose-500/20';
      icon = <X className="w-3 h-3" />;
    }

    return (
      <span
        key={label}
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold border ${color}`}
      >
        <span>{label}</span>
        {icon}
      </span>
    );
  };

  return (
    <div className="bg-[#151921] border border-gray-800 rounded-2xl p-5 hover:border-gray-700 transition-all flex flex-col justify-between shadow-xl relative overflow-hidden group">
      <div className="space-y-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl ${profile.is_builtin ? 'bg-[#5865F2]/10 text-[#5865F2]' : 'bg-amber-500/10 text-amber-400'}`}>
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-bold text-white tracking-wide">
                  {profile.name.replace(/_/g, ' ')}
                </h4>
              </div>
              <div className="flex items-center gap-2 mt-1">
                {profile.is_builtin ? (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-[#5865F2]/20 text-[#5865F2] font-semibold uppercase tracking-wider">
                    BUILT-IN
                  </span>
                ) : (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold uppercase tracking-wider">
                    CUSTOM
                  </span>
                )}
                <span className="text-[10px] px-2 py-0.5 rounded bg-purple-900/30 text-purple-300 font-semibold uppercase tracking-wider border border-purple-800/40">
                  {isVoice ? 'VOICE POLICY' : 'TEXT POLICY'}
                </span>
                {profile.category && (
                  <span className="text-[10px] px-2 py-0.5 rounded bg-gray-800 text-gray-300 font-medium">
                    {profile.category}
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {profile.description && (
          <p className="text-xs text-gray-400 leading-relaxed min-h-[36px]">
            {profile.description}
          </p>
        )}

        {/* Visual Summary Badges */}
        <div className="pt-2 border-t border-gray-800/80">
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider block mb-2">
            Rule Summary
          </span>
          <div className="flex flex-wrap gap-1.5">
            {isVoice ? (
              <>
                {renderRuleBadge('CONNECT', profile.allow_connect)}
                {renderRuleBadge('SPEAK', profile.allow_speak)}
                {renderRuleBadge('VIDEO', profile.allow_video)}
                {renderRuleBadge('STREAM', profile.allow_stream)}
                {renderRuleBadge('SOUNDBOARD', profile.allow_soundboard)}
                {renderRuleBadge('VAD', profile.allow_voice_activity)}
                {renderRuleBadge('PRIORITY', profile.allow_priority_speaker)}
              </>
            ) : (
              <>
                {renderRuleBadge('TEXT', profile.allow_text)}
                {renderRuleBadge('LINKS', profile.allow_links)}
                {renderRuleBadge('IMAGES', profile.allow_images)}
                {renderRuleBadge('VIDEOS', profile.allow_videos)}
                {renderRuleBadge('FILES', profile.allow_files)}
                {renderRuleBadge('STICKERS', profile.allow_stickers)}
                {renderRuleBadge('@EVERYONE', profile.allow_everyone)}
                {renderRuleBadge('MENTIONS', profile.allow_user_mentions)}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-4 mt-4 border-t border-gray-800 text-xs">
        <button
          onClick={() => onApply(profile)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#5865F2] hover:bg-[#4752c4] text-white font-semibold rounded-xl transition-all shadow"
        >
          <span>Apply to Channel</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>

        <div className="flex items-center gap-1">
          {profile.is_builtin && onView && (
            <button
              onClick={() => onView(profile)}
              title="View Built-in Details"
              className="px-2 py-1 text-xs text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors font-medium"
            >
              View
            </button>
          )}

          {onClone && (
            <button
              onClick={() => onClone(profile)}
              title="Duplicate / Create Custom"
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            >
              <Copy className="w-4 h-4" />
            </button>
          )}

          {!profile.is_builtin && onEdit && (
            <button
              onClick={() => onEdit(profile)}
              title="Edit custom policy"
              className="p-1.5 text-gray-400 hover:text-indigo-400 hover:bg-indigo-500/10 rounded-lg transition-colors"
            >
              <Edit3 className="w-4 h-4" />
            </button>
          )}

          {!profile.is_builtin && onDelete && (
            <button
              onClick={() => onDelete(profile.id, profile.name)}
              title="Delete custom policy"
              className="p-1.5 text-gray-400 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition-colors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

