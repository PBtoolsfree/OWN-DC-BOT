import { FastifyInstance } from 'fastify';
import { randomBytes } from 'crypto';
import fetch from 'node-fetch';

const sessions = new Map<string, { ownerId: string; expires: number }>();

export const requireAuth = async (request: any, reply: any) => {
  const sessionId = request.cookies.sessionId;
  if (!sessionId) {
    reply.status(401).send({ error: 'Unauthorized' });
    return;
  }
  
  const session = sessions.get(sessionId);
  if (!session || session.expires < Date.now()) {
    sessions.delete(sessionId);
    reply.clearCookie('sessionId');
    reply.status(401).send({ error: 'Session expired' });
    return;
  }
  
  if (session.ownerId !== process.env.DISCORD_OWNER_ID) {
    reply.status(403).send({ error: 'Forbidden' });
    return;
  }
  
  request.user = { id: session.ownerId };
};

export async function authRoutes(app: FastifyInstance) {
  const OAUTH_SCOPES = 'identify';
  const REDIRECT_URI = \`\${process.env.DASHBOARD_URL}/api/auth/discord/callback\`;

  app.get('/api/auth/discord', async (request, reply) => {
    const state = randomBytes(16).toString('hex');
    reply.setCookie('oauth_state', state, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
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
    reply.clearCookie('oauth_state');

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
        headers: { Authorization: \`Bearer \${tokenData.access_token}\` }
      });
      
      if (!userResponse.ok) {
        reply.redirect('/login?error=user_fetch_failed');
        return;
      }

      const userData = await userResponse.json() as any;

      if (userData.id !== process.env.DISCORD_OWNER_ID) {
        reply.redirect('/login?error=unauthorized_owner');
        return;
      }

      const sessionId = randomBytes(32).toString('hex');
      sessions.set(sessionId, {
        ownerId: userData.id,
        expires: Date.now() + 7 * 24 * 60 * 60 * 1000 // 7 days
      });

      reply.setCookie('sessionId', sessionId, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 7 * 24 * 60 * 60 // 7 days in seconds
      });

      reply.redirect('/');
    } catch (err) {
      reply.redirect('/login?error=internal_error');
    }
  });

  app.post('/api/auth/logout', async (request, reply) => {
    const sessionId = request.cookies.sessionId;
    if (sessionId) {
      sessions.delete(sessionId);
    }
    reply.clearCookie('sessionId', { path: '/' });
    return { success: true };
  });

  app.get('/api/auth/me', { preHandler: requireAuth }, async (request, reply) => {
    return { authenticated: true, ownerId: (request as any).user.id };
  });
}
