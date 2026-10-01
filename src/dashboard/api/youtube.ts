import { FastifyInstance } from 'fastify';
import { requireAuth, logAudit } from './auth';
import { rawClient } from '../../database';
import { z } from 'zod';
import { Client, TextChannel, EmbedBuilder } from 'discord.js';

const channelSchema = z.object({
  id: z.string().min(1),
  discord_channel_id: z.string().min(1),
  channel_url: z.string().url(),
  channel_name: z.string().min(1),
  enabled: z.number().int().min(0).max(1).default(1),
  mention_role_id: z.string().optional(),
  custom_message: z.string().optional()
});

const patchSchema = z.object({
  discord_channel_id: z.string().min(1),
  channel_url: z.string().url(),
  channel_name: z.string().min(1),
  enabled: z.number().int().min(0).max(1),
  mention_role_id: z.string().optional(),
  custom_message: z.string().optional()
}).partial();

export async function youtubeRoutes(app: FastifyInstance, client: Client) {
  app.get('/api/youtube/channels', { preHandler: requireAuth }, async (request, reply) => {
    const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;
    const result = await rawClient.execute({
      sql: 'SELECT * FROM youtube_channels WHERE guild_id = ? ORDER BY rowid DESC',
      args: [guildId]
    });
    return result.rows;
  });

  app.post('/api/youtube/channels', { preHandler: requireAuth }, async (request, reply) => {
    try {
      const data = channelSchema.parse(request.body);
      const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;

      // Validate Discord Destination
      const guild = await client.guilds.fetch(guildId!).catch(() => null);
      if (!guild) return reply.status(400).send({ error: 'Bot is not in the primary guild' });
      
      const channel = await guild.channels.fetch(data.discord_channel_id).catch(() => null);
      if (!channel || !channel.isTextBased()) return reply.status(400).send({ error: 'Invalid Discord channel' });
      
      const me = guild.members.me;
      if (!channel.permissionsFor(me!).has(['SendMessages', 'EmbedLinks'])) {
        return reply.status(400).send({ error: 'Bot missing SendMessages/EmbedLinks permissions in destination channel' });
      }

      await rawClient.execute({
        sql: 'INSERT INTO youtube_channels (id, guild_id, discord_channel_id, channel_url, channel_name, enabled, mention_role_id, custom_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        args: [data.id, guildId, data.discord_channel_id, data.channel_url, data.channel_name, data.enabled, data.mention_role_id || null, data.custom_message || null]
      });

      logAudit('youtube_channel_add', 'youtube', { id: data.id, name: data.channel_name });
      return { success: true, id: data.id };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.delete('/api/youtube/channels/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;
    const id = request.params.id;

    const existing = await rawClient.execute({
      sql: 'SELECT id FROM youtube_channels WHERE id = ? AND guild_id = ?',
      args: [id, guildId]
    });

    if (existing.rows.length === 0) return reply.status(404).send({ error: 'Channel not found' });

    await rawClient.execute({
      sql: 'DELETE FROM youtube_channels WHERE id = ?',
      args: [id]
    });
    
    logAudit('youtube_channel_delete', 'youtube', { id });
    return { success: true };
  });

  app.patch('/api/youtube/channels/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    try {
      const data = patchSchema.parse(request.body);
      const id = request.params.id;
      const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;

      const existing = await rawClient.execute({
        sql: 'SELECT id FROM youtube_channels WHERE id = ? AND guild_id = ?',
        args: [id, guildId]
      });

      if (existing.rows.length === 0) return reply.status(404).send({ error: 'Channel not found' });

      // If updating discord channel, validate it
      if (data.discord_channel_id) {
        const guild = await client.guilds.fetch(guildId!).catch(() => null);
        if (guild) {
          const channel = await guild.channels.fetch(data.discord_channel_id).catch(() => null);
          if (!channel || !channel.isTextBased()) return reply.status(400).send({ error: 'Invalid Discord channel' });
          const me = guild.members.me;
          if (!channel.permissionsFor(me!).has(['SendMessages', 'EmbedLinks'])) {
            return reply.status(400).send({ error: 'Bot missing SendMessages/EmbedLinks permissions in destination channel' });
          }
        }
      }

      const updates: string[] = [];
      const args: any[] = [];

      for (const [key, value] of Object.entries(data)) {
        if (value !== undefined) {
          updates.push(`${key} = ?`);
          args.push(value);
        }
      }

      if (updates.length > 0) {
        args.push(id);
        args.push(guildId);
        await rawClient.execute({
          sql: `UPDATE youtube_channels SET ${updates.join(', ')} WHERE id = ? AND guild_id = ?`,
          args
        });
      }

      logAudit('youtube_channel_edit', 'youtube', { id, updates: data });
      return { success: true };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.post('/api/youtube/channels/:id/test', { preHandler: requireAuth }, async (request: any, reply) => {
    try {
      const id = request.params.id;
      const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;

      const result = await rawClient.execute({
        sql: 'SELECT * FROM youtube_channels WHERE id = ? AND guild_id = ?',
        args: [id, guildId]
      });

      if (result.rows.length === 0) return reply.status(404).send({ error: 'Channel not found' });
      const channelData = result.rows[0];

      const guild = await client.guilds.fetch(guildId!).catch(() => null);
      if (!guild) return reply.status(400).send({ error: 'Guild not found' });

      const channel = await guild.channels.fetch(channelData.discord_channel_id as string).catch(() => null);
      if (!channel || !channel.isTextBased()) return reply.status(400).send({ error: 'Invalid Discord channel' });

      const textChannel = channel as TextChannel;
      
      const embed = new EmbedBuilder()
        .setTitle(`Test Notification: ${channelData.channel_name}`)
        .setDescription('This is a test notification from the PB HERO Dashboard to verify your configuration.')
        .setURL(channelData.channel_url as string)
        .setColor('#FF0000');

      let content = channelData.custom_message as string || '';
      if (channelData.mention_role_id) {
        content = `<@&${channelData.mention_role_id}> ${content}`.trim();
      }

      await textChannel.send({
        content: content || 'Test notification',
        embeds: [embed]
      });

      logAudit('youtube_test_notification', 'youtube', { id });
      return { success: true };
    } catch (err: any) {
      reply.status(500).send({ error: 'Failed to send test notification: ' + err.message });
    }
  });
}
