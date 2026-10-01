import { config } from 'dotenv';
import { startBot } from './bot';
import { startDashboard } from './dashboard';
import { initDatabase } from './database';
import { startYoutubeMonitor } from './youtube';
import pino from 'pino';

export const logger = pino({
  transport: {
    target: 'pino-pretty',
    options: {
      colorize: true
    }
  }
});

config();

async function bootstrap() {
  logger.info('Starting PB HERO Discord Bot...');
  
  try {
    // 1. Init Database
    await initDatabase();
    logger.info('Database initialized.');

    // 2. Start Bot
    const client = await startBot();
    logger.info('Discord bot connected.');

    // 3. Start YouTube Monitor
    startYoutubeMonitor(client);
    logger.info('YouTube monitor started.');

    // 4. Start Dashboard API
    await startDashboard(client);
    logger.info('Dashboard API started.');

  } catch (err) {
    logger.error(err, 'Failed to start application');
    process.exit(1);
  }
}

bootstrap();
