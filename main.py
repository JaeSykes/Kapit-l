import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print("="*60)
    print(f"Bot: {bot.user}")
    print("READY - Bot funguje!")
    print("="*60)

@bot.command(name="capital")
async def capital_command(ctx):
    await ctx.send("TEST - Bot responds! 🎉")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
