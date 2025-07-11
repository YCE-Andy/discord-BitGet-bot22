import os
import discord
from discord.ext import commands

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SOURCE_CHANNEL_ID = int(os.getenv("SOURCE_CHANNEL_ID"))
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID"))

def parse_signal(message):
    lines = message.content.strip().splitlines()
    if not lines or len(lines) < 6:
        return None

    try:
        symbol = lines[0].strip().upper()
        buy_zone_line = next(line for line in lines if "BUYZONE" in line.upper())
        buy_zone = buy_zone_line.upper().replace("BUYZONE", "").strip()

        stop_line = next(line for line in lines if "STOP" in line.upper())
        stop = stop_line.upper().replace("STOP", "").strip()

        leverage_line = next(line for line in lines if "LEVERAGE" in line.upper())
        leverage = leverage_line.upper().replace("LEVERAGE", "").strip()

        # Extract target prices (all lines after "TARGETS")
        targets = []
        try:
            target_start = lines.index("TARGETS") + 1
        except ValueError:
            target_start = next(i for i, l in enumerate(lines) if "TARGETS" in l.upper()) + 1

        for line in lines[target_start:]:
            if line.strip() == "":
                break
            if any(x in line.upper() for x in ["STOP", "LEVERAGE", "BUYZONE"]):
                break
            targets.append(line.strip())

        formatted_targets = "\n".join([f"• {t}" for t in targets])

        formatted_message = (
            f"📢 Trade Signal: **{symbol}**\n"
            f"📉 Buy Zone: {buy_zone}\n"
            f"🎯 Targets:\n{formatted_targets}\n"
            f"🛑 Stop Loss: {stop}\n"
            f"⚡️ Leverage: x{leverage}"
        )
        return formatted_message

    except Exception as e:
        print(f"Error parsing message: {e}")
        return None

@bot.event
async def on_ready():
    print(f"Bot is online as {bot.user}")

@bot.event
async def on_message(message):
    if message.channel.id == SOURCE_CHANNEL_ID and not message.author.bot:
        parsed = parse_signal(message)
        if parsed:
            target_channel = bot.get_channel(TARGET_CHANNEL_ID)
            if target_channel:
                await target_channel.send(parsed)
            else:
                print("Target channel not found")

bot.run(TOKEN)
