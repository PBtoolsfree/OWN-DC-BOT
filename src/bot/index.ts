import { Client, GatewayIntentBits } from 'discord.js';
import { handleModeration } from '../moderation';
import { logger } from '../index';

export async function startBot(): Promise<Client> {
  const client = new Client({
    intents: [
      GatewayIntentBits.Guilds,
      GatewayIntentBits.GuildMessages,
      GatewayIntentBits.MessageContent,
      GatewayIntentBits.GuildMembers,
    ]
  });

  client.on('ready', () => {
    logger.info(`Logged in as ${client.user?.tag}!`);
  });

  client.on('messageCreate', async (message) => {
    if (message.author.bot) return;
    
    // Check moderation rules
    if (process.env.MODERATION_ENABLED === 'true') {
      await handleModeration(message);
    }
  });

  await client.login(process.env.DISCORD_BOT_TOKEN);
  return client;
}
