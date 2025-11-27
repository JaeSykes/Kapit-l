import discord
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
import gspread
import json
import os
from datetime import datetime

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

SERVER_ID = int(os.getenv("GUILD_ID", "1397286059406000249"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "1443610848391204955"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
MESSAGE_IDS_FILE = "capital_message_ids.json"
UPDATE_INTERVAL = 3

print("="*60)
print("CAPITAL BOT")
print("="*60)

def get_sheets_client():
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        creds_dict = json.loads(creds_json)
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"Chyba: {e}")
        return None

def get_capital_data():
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        sheet = client.open_by_key(SHEET_ID).worksheet("Kapital new")
        rows = sheet.range('B4:I21')
        
        if not rows:
            return None
        
        data = []
        for i in range(0, len(rows), 8):
            row_data = rows[i:i+8]
            
            if len(row_data) >= 8 and row_data[0].value and str(row_data[0].value).strip():
                try:
                    name = str(row_data[0].value).strip()
                    qty = float(str(row_data[1].value or 0).replace(",", "."))
                    pct = float(str(row_data[2].value or 0).replace(",", "."))
                    usd = float(str(row_data[3].value or 0).replace(",", "."))
                    it = float(str(row_data[4].value or 0).replace(",", "."))
                    ad = float(str(row_data[5].value or 0).replace(",", "."))
                    zustatek = float(str(row_data[6].value or 0).replace(",", "."))
                    
                    if qty > 0:
                        data.append({
                            "name": name,
                            "qty": qty,
                            "pct": pct,
                            "usd": usd,
                            "it": it,
                            "ad": ad,
                            "zustatek": zustatek
                        })
                except (ValueError, TypeError):
                    continue
        
        return data if data else None
    except Exception as e:
        print(f"Chyba: {e}")
        return None

def format_table(data):
    if not data:
        return "Neni data"
    
    result = "KAPITAL CPD\n"
    result += "=" * 120 + "\n"
    result += f"{'Jmeno':<20} {'Qty':>8} {'%':>7} {'$ Aden':>16} {'-it':>12} {'-ad':>12} {'Zustatek':>16}\n"
    result += "-" * 120 + "\n"
    
    for item in data:
        result += f"{item['name'][:19]:<20} {item['qty']:>8.0f} {item['pct']:>6.2f}% {item['usd']:>15.0f} {item['it']:>11.0f} {item['ad']:>11.0f} {item['zustatek']:>15.0f}\n"
    
    total_qty = sum(d["qty"] for d in data)
    total_pct = sum(d["pct"] for d in data)
    total_usd = sum(d["usd"] for d in data)
    total_it = sum(d["it"] for d in data)
    total_ad = sum(d["ad"] for d in data)
    total_zust = sum(d["zustatek"] for d in data)
    
    result += "-" * 120 + "\n"
    result += f"{'CELKEM':<20} {total_qty:>8.0f} {total_pct:>6.2f}% {total_usd:>15.0f} {total_it:>11.0f} {total_ad:>11.0f} {total_zust:>15.0f}\n"
    result += "=" * 120 + "\n"
    result += f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return result

def load_message_ids():
    if os.path.exists(MESSAGE_IDS_FILE):
        try:
            with open(MESSAGE_IDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"capital_message": None}

def save_message_ids(msg_ids):
    with open(MESSAGE_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(msg_ids, f, ensure_ascii=False, indent=2)

async def update_capital_display():
    try:
        channel = bot.get_channel(CHANNEL_ID)
        guild = bot.get_guild(SERVER_ID)
        
        if not channel or not guild:
            return
        
        data = get_capital_data()
        if not data:
            return
            
        table_text = format_table(data)
        msg_ids = load_message_ids()
        
        if msg_ids["capital_message"]:
            try:
                msg = await channel.fetch_message(int(msg_ids["capital_message"]))
                await msg.edit(content=table_text)
                print(f"Update: {datetime.now().strftime('%H:%M:%S')}")
                return
            except:
                msg_ids["capital_message"] = None
        
        msg = await channel.send(table_text)
        msg_ids["capital_message"] = str(msg.id)
        save_message_ids(msg_ids)
        print(f"Nova zprava: {msg.id}")
        
    except Exception as e:
        print(f"Chyba update: {e}")

@tasks.loop(minutes=UPDATE_INTERVAL)
async def update_capital_task():
    await update_capital_display()

@update_capital_task.before_loop
async def before_update_task():
    await bot.wait_until_ready()

@bot.command(name="capital")
async def capital_command(ctx):
    data = get_capital_data()
    if data:
        table_text = format_table(data)
        await ctx.send(table_text)

@bot.command(name="capital-pin")
@commands.has_permissions(administrator=True)
async def capital_pin(ctx):
    data = get_capital_data()
    if data:
        table_text = format_table(data)
        msg = await ctx.send(table_text)
        msg_ids = load_message_ids()
        msg_ids["capital_message"] = str(msg.id)
        save_message_ids(msg_ids)
        await ctx.send("OK")

@bot.event
async def on_ready():
    print("="*60)
    print(f"Bot: {bot.user}")
    print("="*60)
    
    guild = bot.get_guild(SERVER_ID)
    if guild:
        print(f"Server: {guild.name}")
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            print(f"Kanal: {channel.name}")
            await update_capital_display()
            if not update_capital_task.is_running():
                update_capital_task.start()
            print("="*60)
            print("READY")
            print("="*60)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
