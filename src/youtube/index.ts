import { Client, EmbedBuilder, TextChannel } from 'discord.js';
import { logger } from '../index';
import { rawClient } from '../database';
import { XMLParser } from 'fast-xml-parser';

let pollIntervalSeconds = Number.parseInt(process.env.YOUTUBE_POLL_INTERVAL_SECONDS ?? '120', 10);
if (!Number.isFinite(pollIntervalSeconds) || pollIntervalSeconds < 30 || pollIntervalSeconds > 600) {
  pollIntervalSeconds = 120;
}
const POLL_INTERVAL = pollIntervalSeconds * 1000;

const parser = new XMLParser({
  ignoreAttributes: false,
  attributeNamePrefix: '@_',
});

export function startYoutubeMonitor(client: Client) {
  logger.info(`YouTube monitor started. Polling interval: ${POLL_INTERVAL / 1000} seconds`);

  setInterval(async () => {
    try {
      const result = await rawClient.execute('SELECT * FROM youtube_channels WHERE enabled = 1');
      const channels = result.rows;
      
      if (channels.length === 0) {
        return; // No channels configured
      }

      for (const channel of channels) {
        try {
          await processChannel(client, channel);
        } catch (err) {
          logger.error(`Error processing channel ${channel.channel_name || channel.id}: ${err}`);
        }
      }
    } catch (err) {
      logger.error(err, 'Error in YouTube scheduler loop');
    }
  }, POLL_INTERVAL);
}

async function processChannel(client: Client, channel: any) {
  const channelId = channel.id;
  const guildId = channel.guild_id;
  const discordChannelId = channel.discord_channel_id;

  const url = `https://www.youtube.com/feeds/videos.xml?channel_id=${channelId}`;
  
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} from YouTube`);
  }
  
  const text = await response.text();
  const data = parser.parse(text);
  
  if (!data || !data.feed || !data.feed.entry) {
    return; // No entries or invalid feed
  }

  // Ensure entries is an array (fast-xml-parser returns object if only 1 entry)
  let entries = data.feed.entry;
  if (!Array.isArray(entries)) {
    entries = [entries];
  }

  // Sort entries from oldest to newest to process chronologically
  entries.sort((a: any, b: any) => new Date(a.published).getTime() - new Date(b.published).getTime());

  for (const entry of entries) {
    const videoId = entry['yt:videoId'];
    if (!videoId) continue;
    
    // Check duplicate
    const checkResult = await rawClient.execute({
      sql: 'SELECT 1 FROM youtube_notifications WHERE guild_id = ? AND youtube_channel_id = ? AND video_id = ?',
      args: [guildId, channelId, videoId]
    });

    if (checkResult.rows.length === 0) {
      // It's a new video
      
      // If last_video_id is null, it means channel was just added, skip sending old videos, just store it
      if (channel.last_video_id === null) {
        await rawClient.execute({
          sql: 'INSERT INTO youtube_notifications (guild_id, youtube_channel_id, video_id) VALUES (?, ?, ?)',
          args: [guildId, channelId, videoId]
        });
        await rawClient.execute({
          sql: 'UPDATE youtube_channels SET last_video_id = ? WHERE id = ?',
          args: [videoId, channelId]
        });
        logger.info(`Stored baseline video ${videoId} for newly added channel ${channelId}`);
        continue;
      }
      
      // Send notification
      const discordGuild = client.guilds.cache.get(guildId);
      if (discordGuild) {
        const discordChannel = discordGuild.channels.cache.get(discordChannelId) as TextChannel;
        if (discordChannel) {
          const videoUrl = entry.link['@_href'] || `https://www.youtube.com/watch?v=${videoId}`;
          const title = entry.title;
          const author = entry.author?.name || channel.channel_name || 'YouTube Channel';
          
          let content = channel.custom_message || `🔴 **${author}** just uploaded a new video!`;
          if (channel.mention_role_id) {
            content = `<@&${channel.mention_role_id}> ` + content;
          }

          const embed = new EmbedBuilder()
            .setTitle(title)
            .setURL(videoUrl)
            .setAuthor({ name: author, url: `https://youtube.com/channel/${channelId}` })
            .setImage(`https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`)
            .setColor('#FF0000')
            .setTimestamp(new Date(entry.published));

          await discordChannel.send({ content, embeds: [embed] });
          logger.info(`Sent notification for video ${videoId} to channel ${discordChannelId}`);
        } else {
          logger.warn(`Discord channel ${discordChannelId} not found in guild ${guildId}`);
        }
      }

      // Mark as notified
      await rawClient.execute({
        sql: 'INSERT INTO youtube_notifications (guild_id, youtube_channel_id, video_id) VALUES (?, ?, ?)',
        args: [guildId, channelId, videoId]
      });
      await rawClient.execute({
        sql: 'UPDATE youtube_channels SET last_video_id = ? WHERE id = ?',
        args: [videoId, channelId]
      });
    }
  }
}
