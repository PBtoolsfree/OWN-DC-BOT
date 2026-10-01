import { drizzle } from 'drizzle-orm/libsql';
import { createClient } from '@libsql/client';

export let db: ReturnType<typeof drizzle>;

export async function initDatabase() {
  const client = createClient({
    url: process.env.DATABASE_URL || 'file:./data/database.sqlite',
  });
  
  db = drizzle(client);
  
  // Basic migrations for now
  await client.execute(`
    CREATE TABLE IF NOT EXISTS youtube_channels (
      id TEXT PRIMARY KEY,
      guild_id TEXT NOT NULL,
      discord_channel_id TEXT NOT NULL,
      channel_url TEXT,
      channel_name TEXT,
      last_video_id TEXT,
      enabled INTEGER DEFAULT 1
    )
  `);

  await client.execute(`
    CREATE TABLE IF NOT EXISTS moderation_rules (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      guild_id TEXT NOT NULL,
      rule_type TEXT NOT NULL,
      enabled INTEGER DEFAULT 1,
      config TEXT
    )
  `);
}
