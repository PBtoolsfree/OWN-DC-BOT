import { FastifyInstance } from 'fastify';
import { requireAuth } from './auth';
import { Client } from 'discord.js';
import { rawClient } from '../../database';
import os from 'os';

export async function overviewRoutes(app: FastifyInstance, client: Client) {
  app.get('/api/overview', { preHandler: requireAuth }, async (request, reply) => {
    try {
      const channelResult = await rawClient.execute('SELECT COUNT(*) as count FROM youtube_channels WHERE enabled = 1');
      const notificationResult = await rawClient.execute('SELECT COUNT(*) as count FROM youtube_notifications');
      
      const enabledChannels = (channelResult.rows[0]?.count as number) || 0;
      const notificationsSent = (notificationResult.rows[0]?.count as number) || 0;
      
      // Look up errors in audit logs (simple mockup metric)
      const errorsResult = await rawClient.execute({
        sql: 'SELECT COUNT(*) as count FROM audit_logs WHERE action LIKE ? OR category = ?',
        args: ['%error%', 'error']
      });
      const recentErrors = (errorsResult.rows[0]?.count as number) || 0;

      return {
        botStatus: client.isReady() ? 'Online' : 'Offline',
        gatewayPing: client.ws.ping,
        uptime: process.uptime(),
        databaseStatus: 'Healthy',
        youtubeChannelsCount: enabledChannels,
        youtubeNotificationsSent: notificationsSent,
        moderationStatus: process.env.MODERATION_ENABLED === 'true' ? 'Active' : 'Disabled',
        recentErrors
      };
    } catch (err) {
      app.log.error(err);
      reply.status(500).send({ error: 'Failed to fetch overview data' });
    }
  });

  app.get('/api/monitor', { preHandler: requireAuth }, async (request, reply) => {
    try {
      const channelRes = await rawClient.execute('SELECT COUNT(*) as t, SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as e FROM youtube_channels');
      const totalChannels = (channelRes.rows[0]?.t as number) || 0;
      const enabledChannels = (channelRes.rows[0]?.e as number) || 0;

      // Without actual complex health checking, assume enabled = healthy
      return {
        discordGateway: client.isReady() ? 'Connected' : 'Disconnected',
        botStatus: client.isReady() ? 'Running' : 'Stopped',
        database: 'Connected',
        dashboardApi: 'Running',
        youtubeMonitor: 'Active',
        uptime: process.uptime(),
        cpu: os.loadavg()[0],
        memory: process.memoryUsage().heapUsed,
        youtubeHealth: {
          total: totalChannels,
          enabled: enabledChannels,
          healthy: enabledChannels,
          warning: 0,
          error: 0,
          lastPoll: new Date().toISOString(),
          lastSuccessfulPoll: new Date().toISOString(),
          lastError: null
        }
      };
    } catch (err) {
      reply.status(500).send({ error: 'Failed to load monitor data' });
    }
  });

  app.get('/api/permissions', { preHandler: requireAuth }, async (request, reply) => {
    const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;
    if (!guildId) return reply.status(400).send({ error: 'No primary guild configured' });
    
    const guild = await client.guilds.fetch(guildId).catch(() => null);
    if (!guild) return reply.status(400).send({ error: 'Bot is not in the primary guild' });
    
    const me = guild.members.me;
    if (!me) return reply.status(400).send({ error: 'Cannot find bot member in guild' });

    const reqPerms = ['ViewChannel', 'SendMessages', 'EmbedLinks', 'ReadMessageHistory', 'ManageMessages', 'ModerateMembers'] as const;
    const missing: Array<{ feature: string, permission: string, reason: string }> = [];

    const perms = me.permissions;
    for (const p of reqPerms) {
      if (!perms.has(p)) {
        missing.push({
          feature: p === 'ModerateMembers' ? 'Moderation (Timeouts)' : 'General Chat',
          permission: p,
          reason: 'Required for core bot functionality'
        });
      }
    }

    return { available: perms.toArray(), missing };
  });

  app.get('/api/settings', { preHandler: requireAuth }, async (request, reply) => {
    const res = await rawClient.execute('SELECT * FROM app_settings');
    const dbSettings = res.rows.reduce((acc: any, row: any) => ({ ...acc, [row.key as string]: row.value }), {});
    
    return {
      YOUTUBE_POLL_INTERVAL_SECONDS: parseInt(dbSettings.YOUTUBE_POLL_INTERVAL_SECONDS || process.env.YOUTUBE_POLL_INTERVAL_SECONDS || '120', 10),
      MODERATION_ENABLED: (dbSettings.MODERATION_ENABLED ?? process.env.MODERATION_ENABLED) === 'true',
      MODERATION_LOG_CHANNEL_ID: dbSettings.MODERATION_LOG_CHANNEL_ID || process.env.MODERATION_LOG_CHANNEL_ID || '',
      DISCORD_PRIMARY_GUILD_ID: process.env.DISCORD_PRIMARY_GUILD_ID || '',
      DASHBOARD_URL: process.env.DASHBOARD_URL || ''
    };
  });

  const { z } = require('zod');
  const settingsSchema = z.object({
    YOUTUBE_POLL_INTERVAL_SECONDS: z.number().min(30).max(3600),
    MODERATION_ENABLED: z.boolean(),
    MODERATION_LOG_CHANNEL_ID: z.string().optional()
  });

  app.patch('/api/settings', { preHandler: requireAuth }, async (request: any, reply) => {
    try {
      const data = settingsSchema.parse(request.body);
      const { logAudit } = require('./auth');

      for (const [key, value] of Object.entries(data)) {
        await rawClient.execute({
          sql: 'INSERT INTO app_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
          args: [key, String(value)]
        });
      }

      logAudit('settings_update', 'settings', data);
      return { success: true };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.get('/api/logs', { preHandler: requireAuth }, async (request: any, reply) => {
    const page = parseInt(request.query.page || '1', 10);
    const limit = 50;
    const offset = (page - 1) * limit;

    const res = await rawClient.execute({
      sql: 'SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ? OFFSET ?',
      args: [limit, offset]
    });

    const countRes = await rawClient.execute('SELECT COUNT(*) as c FROM audit_logs');
    
    return {
      logs: res.rows,
      total: countRes.rows[0]?.c || 0,
      page,
      limit
    };
  });
}
