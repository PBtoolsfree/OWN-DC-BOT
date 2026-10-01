import { FastifyInstance } from 'fastify';
import { requireAuth, logAudit } from './auth';
import { rawClient } from '../../database';
import { z } from 'zod';

const ruleSchema = z.object({
  rule_type: z.enum(['banned_words', 'anti_spam', 'anti_links', 'duplicate_messages', 'mention_spam', 'caps']),
  enabled: z.number().int().min(0).max(1).default(1),
  config: z.string()
});

const patchSchema = z.object({
  rule_type: z.enum(['banned_words', 'anti_spam', 'anti_links', 'duplicate_messages', 'mention_spam', 'caps']),
  enabled: z.number().int().min(0).max(1),
  config: z.string()
}).partial();

export async function moderationRoutes(app: FastifyInstance) {
  app.get('/api/moderation/rules', { preHandler: requireAuth }, async (request, reply) => {
    const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;
    const result = await rawClient.execute({
      sql: 'SELECT * FROM moderation_rules WHERE guild_id = ?',
      args: [guildId]
    });
    return result.rows;
  });

  app.post('/api/moderation/rules', { preHandler: requireAuth }, async (request, reply) => {
    try {
      const data = ruleSchema.parse(request.body);
      const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;
      
      const result = await rawClient.execute({
        sql: 'INSERT INTO moderation_rules (guild_id, rule_type, enabled, config) VALUES (?, ?, ?, ?) RETURNING id',
        args: [guildId, data.rule_type, data.enabled, data.config]
      });
      
      logAudit('moderation_rule_add', 'moderation', { id: result.rows[0].id, type: data.rule_type });
      return { success: true, id: result.rows[0].id };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.patch('/api/moderation/rules/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    try {
      const data = patchSchema.parse(request.body);
      const id = request.params.id;
      const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;

      const existing = await rawClient.execute({
        sql: 'SELECT id FROM moderation_rules WHERE id = ? AND guild_id = ?',
        args: [id, guildId]
      });

      if (existing.rows.length === 0) return reply.status(404).send({ error: 'Rule not found' });

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
          sql: `UPDATE moderation_rules SET ${updates.join(', ')} WHERE id = ? AND guild_id = ?`,
          args
        });
      }

      logAudit('moderation_rule_edit', 'moderation', { id, updates: data });
      return { success: true };
    } catch (err: any) {
      reply.status(400).send({ error: err.message || 'Invalid input' });
    }
  });

  app.delete('/api/moderation/rules/:id', { preHandler: requireAuth }, async (request: any, reply) => {
    const id = request.params.id;
    const guildId = process.env.DISCORD_PRIMARY_GUILD_ID;

    const existing = await rawClient.execute({
      sql: 'SELECT id FROM moderation_rules WHERE id = ? AND guild_id = ?',
      args: [id, guildId]
    });

    if (existing.rows.length === 0) return reply.status(404).send({ error: 'Rule not found' });

    await rawClient.execute({
      sql: 'DELETE FROM moderation_rules WHERE id = ?',
      args: [id]
    });
    
    logAudit('moderation_rule_delete', 'moderation', { id });
    return { success: true };
  });
}
