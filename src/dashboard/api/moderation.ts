import { FastifyInstance } from 'fastify';
import { requireAuth } from './auth';
import { rawClient } from '../../database';
import { z } from 'zod';

const ruleSchema = z.object({
  guild_id: z.string(),
  rule_type: z.string(),
  enabled: z.number().int().min(0).max(1).default(1),
  config: z.string()
});

export async function moderationRoutes(app: FastifyInstance) {
  app.get('/api/moderation/rules', { preHandler: requireAuth }, async (request, reply) => {
    const result = await rawClient.execute('SELECT * FROM moderation_rules');
    return result.rows;
  });

  app.post('/api/moderation/rules', { preHandler: requireAuth }, async (request, reply) => {
    try {
      const data = ruleSchema.parse(request.body);
      const result = await rawClient.execute({
        sql: 'INSERT INTO moderation_rules (guild_id, rule_type, enabled, config) VALUES (?, ?, ?, ?) RETURNING id',
        args: [data.guild_id, data.rule_type, data.enabled, data.config]
      });
      return { success: true, id: result.rows[0].id };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.patch('/api/moderation/rules/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    try {
      const data = ruleSchema.partial().parse(request.body);
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
          sql: \`UPDATE moderation_rules SET \${updates.join(', ')} WHERE id = ?\`,
          args
        });
      }

      return { success: true };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.delete('/api/moderation/rules/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    await rawClient.execute({
      sql: 'DELETE FROM moderation_rules WHERE id = ?',
      args: [request.params.id]
    });
    return { success: true };
  });
}
