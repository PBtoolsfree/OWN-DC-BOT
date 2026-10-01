import Fastify from 'fastify';
import cors from '@fastify/cors';
import staticPlugin from '@fastify/static';
import path from 'path';
import { Client } from 'discord.js';
import { logger } from '../index';

export async function startDashboard(client: Client) {
  const app = Fastify({ logger: false });

  await app.register(cors, {
    origin: '*',
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

  // API Routes
  app.get('/api/health', async (request, reply) => {
    return {
      status: 'healthy',
      botStatus: client.isReady() ? 'online' : 'offline',
      uptime: process.uptime()
    };
  });

  app.get('/api/stats', async (request, reply) => {
    return {
      guildCount: client.guilds.cache.size,
      ping: client.ws.ping
    };
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
