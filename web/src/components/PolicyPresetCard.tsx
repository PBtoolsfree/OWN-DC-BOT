import React from 'react';
import { PolicyProfile, PolicyValue } from '../types';
import { Shield, Check, X, Minus, Copy, Trash2, ArrowRight } from 'lucide-react';

interface PolicyPresetCardProps {
  profile: PolicyProfile;
  onApply: (profile: PolicyProfile) => void;
  onClone?: (profile: PolicyProfile) => void;
  onDelete?: (id: number, name: string) => void;
}

export const PolicyPresetCard: React.FC<PolicyPresetCardProps> = ({
  profile,
  onApply,
  onClone,
  onDelete,
}) => {
  const renderRuleBadge = (label: string, value: PolicyValue) => {
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
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold border ${color}`}
      >
        <span>{label}</span>
        {icon}
      </span>
    );
  };

  return (
    <div className="bg-[#151921] border border-gray-800 rounded-xl p-5 hover:border-gray-700 transition-all flex flex-col justify-between shadow-lg">
      <div className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-[#5865F2]/10 text-[#5865F2]">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-white tracking-wide">
                {profile.name.replace(/_/g, ' ')}
              </h4>
              {profile.is_builtin && (
                <span className="text-[10px] text-gray-500 uppercase tracking-wider font-semibold">
                  Built-in Preset
                </span>
              )}
            </div>
          </div>
        </div>

        {profile.description && (
          <p className="text-xs text-gray-400 leading-relaxed min-h-[36px]">
            {profile.description}
          </p>
        )}

        {/* Visual Summary Badges */}
        <div className="pt-2 border-t border-gray-800">
          <span className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider block mb-2">
            Rule Summary
          </span>
          <div className="flex flex-wrap gap-1.5">
            {renderRuleBadge('TEXT', profile.allow_text)}
            {renderRuleBadge('LINKS', profile.allow_links)}
            {renderRuleBadge('IMAGES', profile.allow_images)}
            {renderRuleBadge('VIDEOS', profile.allow_videos)}
            {renderRuleBadge('FILES', profile.allow_files)}
            {renderRuleBadge('MENTIONS', profile.allow_user_mentions)}
            {renderRuleBadge('@EVERYONE', profile.allow_everyone)}
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <div className="flex items-center justify-between pt-4 mt-4 border-t border-gray-800 text-xs">
        <button
          onClick={() => onApply(profile)}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#5865F2] hover:bg-[#4752c4] text-white font-medium rounded-lg transition-colors shadow"
        >
          <span>Apply to Channel</span>
          <ArrowRight className="w-3.5 h-3.5" />
        </button>

        <div className="flex items-center gap-1">
          {onClone && (
            <button
              onClick={() => onClone(profile)}
              title="Clone preset"
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            >
              <Copy className="w-4 h-4" />
            </button>
          )}

          {!profile.is_builtin && onDelete && (
            <button
              onClick={() => onDelete(profile.id, profile.name)}
              title="Delete preset"
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
