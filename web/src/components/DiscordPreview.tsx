import React from 'react';
import { Radio } from 'lucide-react';

interface DiscordPreviewProps {
  title?: string | null;
  description?: string | null;
  footer?: string | null;
  useEmbed?: boolean;
  mentionUser?: boolean;
  mentionTag?: string;
  showAvatar?: boolean;
  showServerIcon?: boolean;
  showTimestamp?: boolean;
  embedColor?: string;
  serverName?: string;
}

export const DiscordPreview: React.FC<DiscordPreviewProps> = ({
  title,
  description,
  footer,
  useEmbed = true,
  mentionUser = true,
  mentionTag = '@NewMember',
  showAvatar = true,
  showServerIcon = true,
  showTimestamp = true,
  embedColor = '#5865F2',
  serverName = 'PB HERO SERVER',
}) => {
  return (
    <div className="space-y-2">
      <span className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
        <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
        Live Discord Preview
      </span>
      <div className="bg-[#313338] rounded-xl p-4 border border-gray-700 shadow-inner select-none font-sans text-sm">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-full bg-[#5865F2] flex items-center justify-center text-white font-bold text-xs shrink-0 shadow">
            BOT
          </div>
          <div className="flex-1 space-y-2 min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-bold text-white text-sm hover:underline cursor-pointer">
                PB HERO BOT
              </span>
              <span className="bg-[#5865F2] text-white text-[10px] font-extrabold px-1 rounded uppercase">
                BOT
              </span>
              <span className="text-gray-400 text-xs">Today at 12:00 PM</span>
            </div>

            {mentionUser && (
              <div className="text-[#c9cdfb] font-medium bg-[#5865f2]/10 inline-block px-1.5 py-0.5 rounded text-xs">
                {mentionTag}
              </div>
            )}

            {useEmbed ? (
              <div
                className="bg-[#2b2d31] rounded p-3.5 space-y-2.5 max-w-lg shadow-sm"
                style={{ borderLeft: `4px solid ${embedColor}` }}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1 flex-1">
                    {title && (
                      <div className="font-bold text-white text-base leading-snug">
                        {title}
                      </div>
                    )}
                    {description && (
                      <div className="text-gray-200 text-xs whitespace-pre-wrap leading-relaxed">
                        {description}
                      </div>
                    )}
                  </div>
                  {showAvatar && (
                    <div className="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center shrink-0 border border-gray-600 shadow">
                      <span className="text-xs font-bold text-gray-300">USER</span>
                    </div>
                  )}
                </div>

                {(footer || showTimestamp) && (
                  <div className="pt-2 border-t border-gray-700/50 flex items-center gap-2 text-[10px] text-gray-400">
                    {showServerIcon && (
                      <div className="w-4 h-4 rounded-full bg-gray-600 flex items-center justify-center text-[8px] text-white font-bold">
                        S
                      </div>
                    )}
                    <span>{footer || serverName}</span>
                    {showTimestamp && (
                      <>
                        <span>•</span>
                        <span>Today at 12:00 PM</span>
                      </>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="text-gray-200 text-xs whitespace-pre-wrap leading-relaxed">
                {title && <div className="font-bold text-white mb-1">{title}</div>}
                {description}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
