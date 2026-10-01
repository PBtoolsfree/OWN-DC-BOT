import { FastifyInstance } from 'fastify';
import { randomBytes, createHash } from 'crypto';
import fetch from 'node-fetch';
import { rawClient } from '../../database';

export const logAudit = async (action: string, category: string, details?: any) => {
  try {
    await rawClient.execute({
      sql: 'INSERT INTO audit_logs (action, category, details) VALUES (?, ?, ?)',
      args: [action, category, details ? JSON.stringify(details) : null]
    });
  } catch (err) {
    console.error('Failed to write audit log', err);
  }
};

export const requireAuth = async (request: any, reply: any) => {
  const sessionId = request.cookies.sessionId;
  if (!sessionId) {
    reply.status(401).send({ error: 'Unauthorized' });
    return;
  }
  
  const hash = createHash('sha256').update(sessionId).digest('hex');
  const sessionResult = await rawClient.execute({
    sql: 'SELECT * FROM dashboard_sessions WHERE session_id_hash = ? AND expires_at > datetime("now")',
    args: [hash]
  });

  if (sessionResult.rows.length === 0) {
    reply.clearCookie('sessionId', { path: '/' });
    reply.status(401).send({ error: 'Session expired or invalid' });
    return;
  }
  
  const session = sessionResult.rows[0];
  if (session.owner_id !== process.env.DISCORD_OWNER_ID) {
    reply.status(403).send({ error: 'Forbidden: Owner only' });
    return;
  }

  // CSRF protection for state-changing operations
  if (['POST', 'PATCH', 'DELETE'].includes(request.method)) {
    const csrfToken = request.headers['x-csrf-token'];
    if (!csrfToken || csrfToken !== '1') {
      // Simplest CSRF: require a custom header because custom headers cannot be set in simple cross-origin forms
      // Since our API and Frontend are same origin, JS can set this header.
      reply.status(403).send({ error: 'CSRF token missing or invalid' });
      return;
    }
  }

  request.user = { id: session.owner_id };
};

export async function authRoutes(app: FastifyInstance) {
  const OAUTH_SCOPES = 'identify';
  const REDIRECT_URI = `${process.env.DASHBOARD_URL}/api/auth/discord/callback`;

  app.get('/api/auth/discord', async (request, reply) => {
    const state = randomBytes(16).toString('hex');
    reply.setCookie('oauth_state', state, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 300 // 5 minutes
    });

    const url = new URL('https://discord.com/api/oauth2/authorize');
    url.searchParams.append('client_id', process.env.DISCORD_CLIENT_ID!);
    url.searchParams.append('redirect_uri', REDIRECT_URI);
    url.searchParams.append('response_type', 'code');
    url.searchParams.append('scope', OAUTH_SCOPES);
    url.searchParams.append('state', state);

    reply.redirect(url.toString());
  });

  app.get('/api/auth/discord/callback', async (request: any, reply) => {
    const { code, state, error } = request.query;
    
    if (error) {
      reply.redirect('/login?error=access_denied');
      return;
    }

    const storedState = request.cookies.oauth_state;
    if (!storedState || state !== storedState) {
      reply.redirect('/login?error=state_mismatch');
      return;
    }
    reply.clearCookie('oauth_state', { path: '/' });

    try {
      const tokenResponse = await fetch('https://discord.com/api/oauth2/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: process.env.DISCORD_CLIENT_ID!,
          client_secret: process.env.DISCORD_CLIENT_SECRET!,
          grant_type: 'authorization_code',
          code: code as string,
          redirect_uri: REDIRECT_URI,
        })
      });

      if (!tokenResponse.ok) {
        reply.redirect('/login?error=oauth_failed');
        return;
      }

      const tokenData = await tokenResponse.json() as any;
      
      const userResponse = await fetch('https://discord.com/api/users/@me', {
        headers: { Authorization: `Bearer ${tokenData.access_token}` }
      });
      
      if (!userResponse.ok) {
        reply.redirect('/login?error=user_fetch_failed');
        return;
      }

      const userData = await userResponse.json() as any;

      if (userData.id !== process.env.DISCORD_OWNER_ID) {
        logAudit('login_failed', 'authentication', { reason: 'not_owner', id: userData.id });
        reply.redirect('/login?error=unauthorized_owner');
        return;
      }

      const sessionId = randomBytes(32).toString('hex');
      const hash = createHash('sha256').update(sessionId).digest('hex');
      const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();

      await rawClient.execute({
        sql: 'INSERT INTO dashboard_sessions (session_id_hash, owner_id, expires_at) VALUES (?, ?, ?)',
        args: [hash, userData.id, expiresAt]
      });

      reply.setCookie('sessionId', sessionId, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 7 * 24 * 60 * 60 // 7 days in seconds
      });

      logAudit('login_success', 'authentication');
      reply.redirect('/');
    } catch (err) {
      reply.redirect('/login?error=internal_error');
    }
  });

  app.post('/api/auth/logout', async (request, reply) => {
    const sessionId = request.cookies.sessionId;
    if (sessionId) {
      const hash = createHash('sha256').update(sessionId).digest('hex');
      await rawClient.execute({
        sql: 'DELETE FROM dashboard_sessions WHERE session_id_hash = ?',
        args: [hash]
      });
    }
    reply.clearCookie('sessionId', { path: '/' });
    logAudit('logout', 'authentication');
    return { success: true };
  });

  app.get('/api/auth/me', { preHandler: requireAuth }, async (request, reply) => {
    return { authenticated: true, ownerId: (request as any).user.id };
  });
}
