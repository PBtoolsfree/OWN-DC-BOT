import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import request from 'supertest';
import Fastify from 'fastify';
import cookie from '@fastify/cookie';
import { authRoutes } from '../src/dashboard/api/auth';
import { overviewRoutes } from '../src/dashboard/api/overview';
import { youtubeRoutes } from '../src/dashboard/api/youtube';
import { moderationRoutes } from '../src/dashboard/api/moderation';
import { initDatabase, rawClient } from '../src/database';
import { randomBytes, createHash } from 'crypto';

const app = Fastify();

describe('Dashboard API Tests', () => {
  let sessionId = '';
  
  beforeAll(async () => {
    // Setup env
    process.env.DISCORD_OWNER_ID = '12345';
    process.env.DISCORD_PRIMARY_GUILD_ID = '99999';
    process.env.SESSION_SECRET = 'secret';
    process.env.DATABASE_URL = 'file:./test.sqlite';
    
    await initDatabase();
    await app.register(cookie, { secret: 'secret' });
    
    await app.register(authRoutes);
    await app.register(youtubeRoutes, {} as any); // mock client
    await app.register(moderationRoutes);
    // Don't register overview as it depends on discord client in this test mockup context
    
    await app.ready();

    // Create session
    sessionId = randomBytes(32).toString('hex');
    const hash = createHash('sha256').update(sessionId).digest('hex');
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
    await rawClient.execute({
      sql: 'INSERT INTO dashboard_sessions (session_id_hash, owner_id, expires_at) VALUES (?, ?, ?)',
      args: [hash, '12345', expiresAt]
    });
  });

  afterAll(async () => {
    await app.close();
  });

  it('rejects unauthenticated requests', async () => {
    const res = await request(app.server).get('/api/youtube/channels');
    expect(res.status).toBe(401);
  });

  it('rejects without CSRF token on POST', async () => {
    const res = await request(app.server)
      .post('/api/youtube/channels')
      .set('Cookie', \`sessionId=\${sessionId}\`)
      .send({});
    expect(res.status).toBe(403);
  });

  it('validates Youtube creation', async () => {
    const res = await request(app.server)
      .post('/api/youtube/channels')
      .set('Cookie', \`sessionId=\${sessionId}\`)
      .set('x-csrf-token', '1')
      .send({
        id: 'UC123',
        channel_name: 'Test',
        discord_channel_id: '888',
        channel_url: 'https://youtube.com/channel/UC123'
      });
    // Will fail at discord validation step because client is mocked, but should be 400 not 401/403
    expect(res.status).toBe(400);
  });

  it('fetches moderation rules', async () => {
    const res = await request(app.server)
      .get('/api/moderation/rules')
      .set('Cookie', \`sessionId=\${sessionId}\`);
    expect(res.status).toBe(200);
    expect(Array.isArray(res.body)).toBe(true);
  });
});
