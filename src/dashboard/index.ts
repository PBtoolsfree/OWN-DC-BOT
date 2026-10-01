import Fastify from 'fastify';
import cors from '@fastify/cors';
import staticPlugin from '@fastify/static';
import path from 'path';
import { Client } from 'discord.js';
import { logger } from '../index';

export async function startDashboard(client: Client) {
  const app = Fastify({ logger: false });

  await app.register(cors, {
    origin: process.env.DASHBOARD_URL || false, // Exact origin or disable
  });

  // Serve the React frontend in production
  if (process.env.NODE_ENV === 'production') {
    await app.register(staticPlugin, {
      root: path.join(__dirname, '../../web/dist'),
      prefix: '/',
    });
    
    app.setNotFoundHandler((req, reply) => {
      reply.sendFile('index.html');
    });
  }

  await app.register(import('@fastify/cookie'), {
    secret: process.env.SESSION_SECRET || 'fallback-secret-key-1234567890',
  });

  const { authRoutes } = await import('./api/auth');
  const { overviewRoutes } = await import('./api/overview');
  const { youtubeRoutes } = await import('./api/youtube');
  const { moderationRoutes } = await import('./api/moderation');

  await app.register(authRoutes);
  await app.register(async (instance) => {
    await overviewRoutes(instance, client);
  });
  await app.register(youtubeRoutes);
  await app.register(moderationRoutes);

  app.get('/api/health', async () => {
    return { status: 'healthy', botStatus: client.isReady() ? 'online' : 'offline', uptime: process.uptime() };
  });

  const port = parseInt(process.env.DASHBOARD_PORT || '3000');
  
  try {
    await app.listen({ port, host: '0.0.0.0' });
    logger.info(`Dashboard API listening on port ${port}`);
  } catch (err) {
    app.log.error(err);
    process.exit(1);
  }
}
