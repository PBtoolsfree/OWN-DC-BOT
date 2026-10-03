import React from 'react';
import { ExternalLink, Youtube } from 'lucide-react';

interface NotificationPreviewProps {
  title: string;
  description: string;
  footer?: string;
  mentionRoleName?: string;
  showThumbnail?: boolean;
  showTimestamp?: boolean;
  enableButton?: boolean;
  videoTitle?: string;
  channelName?: string;
}

export const NotificationPreview: React.FC<NotificationPreviewProps> = ({
  title,
  description,
  footer = 'PB HERO Personal Bot',
  mentionRoleName,
  showThumbnail = true,
  showTimestamp = true,
  enableButton = true,
  videoTitle = 'EPIC LIVESTREAM: PB HERO Discord Bot Walkthrough',
  channelName = 'PB HERO',
}) => {
  return (
    <div className="bg-[#313338] border border-[#232428] rounded-xl p-4 max-w-lg shadow-xl font-sans text-sm text-[#dbdee1]">
      {/* Bot message header */}
      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-full bg-[#5865F2] flex items-center justify-center font-bold text-white text-sm shadow">
          PB
        </div>
        <div>
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-white text-sm hover:underline cursor-pointer">
              PB HERO
            </span>
            <span className="bg-[#5865F2] text-[10px] uppercase font-bold text-white px-1 rounded">
              BOT
            </span>
            <span className="text-[11px] text-[#949ba4] ml-1">Today at 12:00 PM</span>
          </div>
        </div>
      </div>

      {/* Role Mention */}
      {mentionRoleName && (
        <div className="mb-2">
          <span className="bg-[#5865F2]/20 text-[#c9cdfb] px-1 py-0.5 rounded text-xs font-medium">
            @{mentionRoleName}
          </span>
        </div>
      )}

      {/* Discord Embed */}
      <div className="border-l-4 border-[#ED4245] bg-[#2b2d31] rounded-r-lg p-3.5 space-y-2">
        {/* Author */}
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded-full bg-red-600 flex items-center justify-center text-[10px] text-white font-bold">
            <Youtube className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-semibold text-white">{channelName}</span>
        </div>

        {/* Title */}
        <h4 className="text-base font-bold text-white hover:text-[#00a8fc] cursor-pointer transition-colors leading-snug">
          {title || '🔴 PB HERO IS LIVE!'}
        </h4>

        {/* Video Subtitle / Dynamic title */}
        <p className="text-xs font-medium text-[#f2f3f5]">{videoTitle}</p>

        {/* Description */}
        {description && (
          <p className="text-xs text-[#dbdee1] leading-relaxed whitespace-pre-wrap">{description}</p>
        )}

        {/* Thumbnail mockup */}
        {showThumbnail && (
          <div className="mt-2 rounded-lg overflow-hidden border border-[#1e1f22] bg-[#1e1f22] aspect-video relative flex items-center justify-center">
            <div className="text-center p-4">
              <Youtube className="w-10 h-10 text-red-500 mx-auto mb-1 opacity-80" />
              <span className="text-xs text-gray-400 font-medium">YouTube Video Thumbnail</span>
            </div>
            <span className="absolute bottom-2 right-2 bg-black/80 text-[10px] text-white px-1.5 py-0.5 rounded font-mono">
              LIVE
            </span>
          </div>
        )}

        {/* Footer & Timestamp */}
        <div className="flex items-center gap-1.5 text-[11px] text-[#949ba4] pt-1">
          {footer && <span>{footer}</span>}
          {footer && showTimestamp && <span>•</span>}
          {showTimestamp && <span>Just now</span>}
        </div>
      </div>

      {/* Action Button */}
      {enableButton && (
        <div className="mt-2.5">
          <button
            type="button"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-[#4e5058] hover:bg-[#6d6f78] text-white text-xs font-medium rounded transition-colors"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            <span>Watch on YouTube</span>
          </button>
        </div>
      )}
    </div>
  );
};
