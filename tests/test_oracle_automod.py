import asyncio
import logging
import sys
from datetime import datetime
import discord
from app.config import get_settings
from app.moderation.engine import ModerationEngine
from app.database.engine import init_engine, close_engine, get_session_direct
from app.database.repositories import ModerationCaseRepo, AutomodRuleRepo

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("test_automod")

class ProxyMessage:
    def __init__(self, real_msg, mock_author):
        self._real = real_msg
        self.author = mock_author
        self.guild = real_msg.guild
        self.channel = real_msg.channel
        self.id = real_msg.id
        self.content = real_msg.content
        self.created_at = real_msg.created_at
        self.attachments = real_msg.attachments
        self.embeds = real_msg.embeds
        self.mention_everyone = False
        self.raw_mentions = []
        self.raw_role_mentions = []
        self.stickers = []

    def __getattr__(self, name):
        return getattr(self._real, name)

    async def delete(self):
        return await self._real.delete()

async def main():
    settings = get_settings()
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    await init_engine()

    @client.event
    async def on_ready():
        logger.info(f"Test client connected: {client.user} to guild {settings.DISCORD_GUILD_ID}")
        guild = client.get_guild(settings.DISCORD_GUILD_ID)
        assert guild is not None, "Guild not found"

        engine = ModerationEngine(client, settings.DISCORD_GUILD_ID)
        await engine.refresh_cache()

        spam_rule = next((r for r in engine._automod_rules_cache if r["rule_type"] == "message_spam"), None)
        logger.info(f"Loaded message_spam rule: {spam_rule}")
        assert spam_rule is not None, "message_spam rule not found in cache"
        assert spam_rule["threshold"] == 3, f"Expected threshold 3, got {spam_rule['threshold']}"
        assert spam_rule["time_window"] == 10, f"Expected time_window 10, got {spam_rule['time_window']}"
        assert spam_rule["action"] == "delete", f"Expected action delete, got {spam_rule['action']}"

        # Channel 1328794251810570302 is bot-cmnd, 1328794247784169495 is general-chat
        channel = guild.get_channel(1328794251810570302) or guild.get_channel(1328794247784169495)
        logger.info(f"Testing in channel: #{channel.name} ({channel.id})")

        test_member = None
        for m in guild.members:
            if not m.bot and not m.guild_permissions.administrator and m.id != guild.owner_id:
                test_member = m
                break
        
        if not test_member:
            logger.error("No non-admin member found in guild")
            await client.close()
            return

        logger.info(f"Using test non-admin member: {test_member.name} ({test_member.id})")

        engine.spam_tracker.clear()

        # Message 1: test1
        msg1_raw = await channel.send("🧪 AutoMod Test Message 1: test1")
        pmsg1 = ProxyMessage(msg1_raw, test_member)
        pmsg1.content = "test1"
        res1 = await engine.process_message(pmsg1)
        logger.info(f"Result for message 1 ('test1'): {res1}")
        assert res1 is None, "Message 1 should be allowed"

        # Message 2: test2
        msg2_raw = await channel.send("🧪 AutoMod Test Message 2: test2")
        pmsg2 = ProxyMessage(msg2_raw, test_member)
        pmsg2.content = "test2"
        res2 = await engine.process_message(pmsg2)
        logger.info(f"Result for message 2 ('test2'): {res2}")
        assert res2 is None, "Message 2 should be allowed"

        # Message 3: test3 (THRESHOLD REACHED!)
        msg3_raw = await channel.send("🧪 AutoMod Test Message 3: test3")
        pmsg3 = ProxyMessage(msg3_raw, test_member)
        pmsg3.content = "test3"
        res3 = await engine.process_message(pmsg3)
        logger.info(f"Result for message 3 ('test3'): {res3}")
        assert res3 is not None, "Message 3 should trigger violation!"
        assert res3["rule"] == "message_spam", f"Expected rule message_spam, got {res3['rule']}"
        assert res3["action"] == "delete", f"Expected action delete, got {res3['action']}"

        # Execute enforcement
        logger.info("Executing handle_violation on message 3...")
        await engine.handle_violation(pmsg3, res3)

        # Verify message 3 was deleted from Discord
        await asyncio.sleep(1)
        try:
            await channel.fetch_message(msg3_raw.id)
            logger.error(f"Message {msg3_raw.id} still exists in Discord!")
            assert False, "Message 3 was not deleted"
        except discord.NotFound:
            logger.info(f"✅ Verified: Message {msg3_raw.id} was successfully deleted from Discord!")

        # Clean up messages 1 and 2
        try:
            await msg1_raw.delete()
            await msg2_raw.delete()
        except Exception:
            pass

        # Verify DB case record
        session = await get_session_direct()
        try:
            latest_cases = await ModerationCaseRepo.get_for_user(session, user_id=test_member.id, limit=5)
            matching_case = next((c for c in latest_cases if c.rule == "message_spam"), None)
            assert matching_case is not None, "No moderation case found for message_spam in DB"
            logger.info(f"✅ Verified DB Case: #{matching_case.case_number} ({matching_case.case_id}) action={matching_case.action} rule={matching_case.rule} reason={matching_case.reason}")
        finally:
            await session.close()

        # Verify Mod Log channel received embed
        mod_log_channel = guild.get_channel(settings.MOD_LOG_CHANNEL_ID)
        if mod_log_channel:
            found_embed = False
            async for m in mod_log_channel.history(limit=5):
                if m.author.id == client.user.id and m.embeds:
                    for emb in m.embeds:
                        if "Automod Violation: Message Spam" in (emb.title or ""):
                            logger.info(f"✅ Verified Discord Mod Log Embed in #{mod_log_channel.name}: {emb.title} - {emb.description}")
                            found_embed = True
                            break
                    if found_embed:
                        break
            assert found_embed, "Mod log embed not found in #auto-mod channel"

        logger.info("🎉 REAL ORACLE AUTOMOD TEST PASSED COMPLETELY!")
        await client.close()

    try:
        await client.start(settings.DISCORD_BOT_TOKEN)
    finally:
        await close_engine()

if __name__ == "__main__":
    asyncio.run(main())
