import { Message } from 'discord.js';
import { logger } from '../index';

export async function handleModeration(message: Message) {
  // Basic example of banned words moderation
  // In a real scenario, these rules are fetched from the database and cached.
  const content = message.content.toLowerCase();
  const bannedWords = ['spamword1', 'badword2']; // This should come from DB

  for (const word of bannedWords) {
    if (content.includes(word)) {
      try {
        await message.delete();
        logger.info(`Deleted message from ${message.author.tag} due to banned word: ${word}`);
        
        if (process.env.MODERATION_LOG_CHANNEL_ID) {
          const logChannel = message.guild?.channels.cache.get(process.env.MODERATION_LOG_CHANNEL_ID);
          if (logChannel && logChannel.isTextBased()) {
            await logChannel.send(`Deleted message from ${message.author.tag} in ${message.channel.toString()} for banned word.`);
          }
        }
        break; // Stop checking after deleting
      } catch (err) {
        logger.error(`Failed to delete message: ${err}`);
      }
    }
  }
}
