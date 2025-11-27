import discord
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
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

print("="*60)
print("CAPITAL BOT")
print("="*60)
print(f"SHEET_ID: {SHEET_ID}")

def get_sheets_client():
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            print("❌ GOOGLE_CREDENTIALS not found!")
            return None
            
        creds_dict = json.loads(creds_json)
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        print("✅ Google Sheets client OK")
        return client
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_capital_data():
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        print(f"Opening sheet {SHEET_ID}...")
        sheet = client.open_by_key(SHEET_ID).worksheet("Kapital new")
        print("✅ Sheet opened")
        
        rows = sheet.range('B4:I21')
        print(f"✅ Got {len(rows)} cells")
        
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
                except (ValueError, TypeError) as e:
                    print(f"Parse error: {e}")
                    continue
        
        print(f"✅ Got {len(data)} rows of data")
        return data if data else None
    except Exception as e:
        print(f"❌ Error reading sheets: {e}")
        import traceback
        traceback.print_exc()
        return None

def format_table(data):
    if not data:
        return "No data available"
    
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

@bot.command(name="capital")
async def capital_command(ctx):
    print("Command: !capital")
    data = get_capital_data()
    if data:
        table_text = format_table(data)
        await ctx.send(f"```\n{table_text}\n```")
    else:
        await ctx.send("❌ Cannot read data from Google Sheets")

@bot.command(name="test")
async def test(ctx):
    await ctx.send("✅ Bot works!")

@bot.event
async def on_ready():
    print("="*60)
    print(f"Bot: {bot.user}")
    print("="*60)
    print("READY")
    print("="*60)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
