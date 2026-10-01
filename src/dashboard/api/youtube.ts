import { FastifyInstance } from 'fastify';
import { requireAuth } from './auth';
import { rawClient } from '../../database';
import { z } from 'zod';
import { randomUUID } from 'crypto';

const channelSchema = z.object({
  id: z.string().min(1),
  guild_id: z.string(),
  discord_channel_id: z.string(),
  channel_name: z.string(),
  enabled: z.number().int().min(0).max(1).default(1),
  mention_role_id: z.string().optional(),
  custom_message: z.string().optional()
});

export async function youtubeRoutes(app: FastifyInstance) {
  app.get('/api/youtube/channels', { preHandler: requireAuth }, async (request, reply) => {
    const result = await rawClient.execute('SELECT * FROM youtube_channels ORDER BY rowid DESC');
    return result.rows;
  });

  app.post('/api/youtube/channels', { preHandler: requireAuth }, async (request, reply) => {
    try {
      const data = channelSchema.parse(request.body);
      
      await rawClient.execute({
        sql: 'INSERT INTO youtube_channels (id, guild_id, discord_channel_id, channel_url, channel_name, enabled, mention_role_id, custom_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        args: [data.id, data.guild_id, data.discord_channel_id, \`https://youtube.com/channel/\${data.id}\`, data.channel_name, data.enabled, data.mention_role_id || null, data.custom_message || null]
      });

      return { success: true, id: data.id };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.delete('/api/youtube/channels/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    await rawClient.execute({
      sql: 'DELETE FROM youtube_channels WHERE id = ?',
      args: [request.params.id]
    });
    return { success: true };
  });

  app.patch('/api/youtube/channels/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    try {
      const data = channelSchema.partial().parse(request.body);
      const id = request.params.id;

      const updates: string[] = [];
      const args: any[] = [];

      for (const [key, value] of Object.entries(data)) {
        if (value !== undefined) {
          updates.push(\`\${key} = ?\`);
          args.push(value);
        }
      }

      if (updates.length > 0) {
        args.push(id);
        await rawClient.execute({
          sql: \`UPDATE youtube_channels SET \${updates.join(', ')} WHERE id = ?\`,
          args
        });
      }

      return { success: true };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });
}
