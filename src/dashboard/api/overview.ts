import { FastifyInstance } from 'fastify';
import { requireAuth } from './auth';
import { Client } from 'discord.js';
import { rawClient } from '../../database';

export async function overviewRoutes(app: FastifyInstance, client: Client) {
  app.get('/api/overview', { preHandler: requireAuth }, async (request, reply) => {
    try {
      const channelResult = await rawClient.execute('SELECT COUNT(*) as count FROM youtube_channels WHERE enabled = 1');
      const notificationResult = await rawClient.execute('SELECT COUNT(*) as count FROM youtube_notifications');
      
      const enabledChannels = (channelResult.rows[0]?.count as number) || 0;
      const notificationsSent = (notificationResult.rows[0]?.count as number) || 0;

      return {
        botStatus: client.isReady() ? 'Online' : 'Offline',
        gatewayPing: client.ws.ping,
        uptime: process.uptime(),
        databaseStatus: 'Healthy',
        youtubeChannelsCount: enabledChannels,
        youtubeNotificationsSent: notificationsSent,
        moderationStatus: process.env.MODERATION_ENABLED === 'true' ? 'Active' : 'Disabled',
        recentErrors: 0 // Mocked for now, can implement actual error log counting later
      };
    } catch (err) {
      app.log.error(err);
      reply.status(500).send({ error: 'Failed to fetch overview data' });
    }
  });
}
