import React from 'react';
import { Radio, ExternalLink } from 'lucide-react';
import { GreetingButton } from '../types';

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
  serverIconUrl?: string | null;
  serverBannerUrl?: string | null;
  avatarUrl?: string | null;
  authorText?: string | null;
  authorIconUrl?: string | null;
  bannerUrl?: string | null;
  bannerMode?: 'none' | 'server' | 'custom' | string | null;
  buttons?: GreetingButton[] | string | null;
  showInviter?: boolean;
  showInviteCode?: boolean;
  memberCount?: number;
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
  serverIconUrl,
  serverBannerUrl,
  avatarUrl,
  authorText,
  authorIconUrl,
  bannerUrl,
  bannerMode = 'none',
  buttons,
}) => {
  // Parse buttons
  let parsedButtons: GreetingButton[] = [];
  if (Array.isArray(buttons)) {
    parsedButtons = buttons.filter((b) => b && b.enabled);
  } else if (typeof buttons === 'string' && buttons.trim()) {
    try {
      const bList = JSON.parse(buttons);
      if (Array.isArray(bList)) {
        parsedButtons = bList.filter((b) => b && b.enabled);
      }
    } catch {
      // Ignored if invalid json in preview
    }
  }

  // Determine effective banner URL
  let effectiveBanner: string | null = null;
  if (bannerMode === 'custom' && bannerUrl) {
    effectiveBanner = bannerUrl;
  } else if (bannerMode === 'server' && serverBannerUrl) {
    effectiveBanner = serverBannerUrl;
  }

  const getButtonStyle = (style?: string) => {
    switch (style) {
      case 'primary':
        return 'bg-[#5865F2] hover:bg-[#4752C4] text-white';
      case 'success':
        return 'bg-[#248046] hover:bg-[#1a6334] text-white';
      case 'danger':
        return 'bg-[#DA373C] hover:bg-[#a1282c] text-white';
      case 'secondary':
        return 'bg-[#4E5058] hover:bg-[#6D6F78] text-white';
      case 'link':
      default:
        return 'bg-[#4E5058] hover:bg-[#6D6F78] text-[#DBDEE1]';
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-bold text-gray-400 uppercase tracking-wider flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-emerald-400 animate-pulse" />
          Live Discord Preview
        </span>
        <span className="text-[11px] text-gray-400 font-mono">
          {serverName}
        </span>
      </div>
      <div className="bg-[#313338] rounded-xl p-4 border border-gray-700 shadow-inner select-none font-sans text-sm">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-full bg-[#5865F2] flex items-center justify-center text-white font-bold text-xs shrink-0 shadow overflow-hidden">
            {serverIconUrl ? (
              <img src={serverIconUrl} alt="Bot" className="w-full h-full object-cover" />
            ) : (
              'BOT'
            )}
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
                className="bg-[#2b2d31] rounded-lg p-3.5 space-y-2.5 max-w-lg shadow-sm"
                style={{ borderLeft: `4px solid ${embedColor}` }}
              >
                {/* Author row */}
                {authorText && (
                  <div className="flex items-center gap-2 text-xs font-medium text-white mb-1">
                    {authorIconUrl && (
                      <img
                        src={authorIconUrl}
                        alt="Author"
                        className="w-5 h-5 rounded-full object-cover"
                        onError={(e) => { (e.target as HTMLElement).style.display = 'none'; }}
                      />
                    )}
                    <span>{authorText}</span>
                  </div>
                )}

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
                    <div className="w-12 h-12 rounded-full bg-gray-700 flex items-center justify-center shrink-0 border border-gray-600 shadow overflow-hidden">
                      {avatarUrl ? (
                        <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
                      ) : (
                        <span className="text-xs font-bold text-gray-300">USER</span>
                      )}
                    </div>
                  )}
                </div>

                {/* Banner Image */}
                {effectiveBanner && (
                  <div className="mt-2 rounded-lg overflow-hidden border border-gray-700/60 max-h-48 bg-black/20">
                    <img
                      src={effectiveBanner}
                      alt="Banner Preview"
                      className="w-full h-auto max-h-48 object-cover"
                      onError={(e) => {
                        (e.target as HTMLElement).style.display = 'none';
                      }}
                    />
                  </div>
                )}

                {(footer || showTimestamp) && (
                  <div className="pt-2 border-t border-gray-700/50 flex items-center gap-2 text-[10px] text-gray-400">
                    {showServerIcon && (
                      <div className="w-4 h-4 rounded-full bg-gray-600 flex items-center justify-center text-[8px] text-white font-bold overflow-hidden">
                        {serverIconUrl ? (
                          <img src={serverIconUrl} alt="S" className="w-full h-full object-cover" />
                        ) : (
                          'S'
                        )}
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

            {/* Discord Buttons Row */}
            {parsedButtons.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 pt-1 max-w-lg">
                {parsedButtons.map((btn) => (
                  <a
                    key={btn.id}
                    href={btn.url || '#'}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition cursor-pointer shadow-sm ${getButtonStyle(
                      btn.style
                    )}`}
                    onClick={(e) => e.preventDefault()}
                  >
                    {btn.emoji && <span>{btn.emoji}</span>}
                    <span>{btn.label || 'Link'}</span>
                    <ExternalLink className="w-3 h-3 opacity-60 ml-0.5" />
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
