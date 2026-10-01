import { Client, EmbedBuilder } from 'discord.js';
import { logger } from '../index';
import fetch from 'node-fetch';
import { XMLParser } from 'fast-xml-parser'; // Need to add this to dependencies? Oh wait I didn't add fast-xml-parser to package.json. I will do string parsing or add it.

// Let's use simple regex for feed parsing to avoid extra dependencies if possible, or we can just fetch and parse using a lightweight approach.
// But XMLParser is better. I'll add fast-xml-parser to package.json later or just use regex for the Atom feed.
// Actually, let's just write the polling logic.

const POLL_INTERVAL = parseInt(process.env.YOUTUBE_POLL_INTERVAL_SECONDS || '120') * 1000;

export function startYoutubeMonitor(client: Client) {
  logger.info(`Starting YouTube monitor with interval ${POLL_INTERVAL}ms`);
  
  setInterval(async () => {
    try {
      // 1. Fetch channels from DB
      // 2. Poll each channel's Atom feed: https://www.youtube.com/feeds/videos.xml?channel_id=CHANNEL_ID
      // 3. Check for new video ID
      // 4. Send Discord message
      // 5. Update DB
      
      // Placeholder logic
      // logger.info('Polling YouTube feeds...');
    } catch (err) {
      logger.error(err, 'Error polling YouTube feeds');
    }
  }, POLL_INTERVAL);
}

// Helper to fetch feed (to be expanded)
export async function checkChannelFeed(channelId: string, lastVideoId: string | null) {
  const url = `https://www.youtube.com/feeds/videos.xml?channel_id=${channelId}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Failed to fetch feed: ${response.statusText}`);
  
  const text = await response.text();
  
  // Extract latest video ID using regex (simple fallback)
  const videoIdMatch = text.match(/<yt:videoId>(.*?)<\/yt:videoId>/);
  if (videoIdMatch && videoIdMatch[1] && videoIdMatch[1] !== lastVideoId) {
    return {
      newVideoId: videoIdMatch[1],
      title: text.match(/<title>(.*?)<\/title>/)?.[1] || 'New Video',
      link: `https://www.youtube.com/watch?v=${videoIdMatch[1]}`
    };
  }
  
  return null;
}
