import discord
from discord.ext import commands, tasks
from google.oauth2.service_account import Credentials
import gspread
import json
import os
from datetime import datetime
import re

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

SERVER_ID = int(os.getenv("GUILD_ID", "1397286059406000249"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "1443610848391204955"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = "Majetek sharing"

print("="*60)
print("CAPITAL BOT")
print("="*60)
print(f"SHEET_ID: {SHEET_ID}")
print(f"SHEET_NAME: {SHEET_NAME}")

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

def clean_number(value):
    """Vyčistit číslo - odstranit speciální znaky a formátování"""
    if not value:
        return 0.0
    
    # Konvertuj na string a odstraň všechny non-breaking spaces
    s = str(value).replace('\xa0', '').replace(' ', '').strip()
    
    # Odstraň všechny znaky která nejsou čísla, tečka, minus
    s = re.sub(r'[^\d.,\-]', '', s)
    
    # Zaměň čárku za tečku
    s = s.replace(',', '.')
    
    try:
        return float(s) if s and s != '-' else 0.0
    except:
        return 0.0

def get_capital_data():
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        print(f"Opening sheet {SHEET_ID}...")
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        print("✅ Sheet opened")
        
        # SPRÁVNÉ: Čti B-I (bez C), řádky 2-32
        # B=Jméno, D=Qty, E=%, F=USD, G=IT, H=AD, I=Zůstatek
        all_cells = sheet.range('B2:I32')
        print(f"✅ Got {len(all_cells)} cells")
        
        if not len(all_cells) < 8:
            data = []
            for i in range(0, len(all_cells), 8):  # 8 sloupců (B-I)
                row_data = all_cells[i:i+8]
                
                if len(row_data) >= 1 and row_data[0].value:
                    name = str(row_data[0].value).strip()
                    
                    # Přeskočit prázdné řádky, nadpisy a sumy
                    if not name or name.lower() in ['celkem', 'celk', 'suma', '', 'jmeno'] or 'celkem' in name.lower():
                        continue
                    
                    try:
                        # B=name, C=skip, D=qty, E=pct, F=usd, G=it, H=ad, I=zustatek
                        qty = clean_number(row_data[2].value if len(row_data) > 2 else 0)  # D
                        pct = clean_number(row_data[3].value if len(row_data) > 3 else 0)  # E
                        usd = clean_number(row_data[4].value if len(row_data) > 4 else 0)  # F
                        it = clean_number(row_data[5].value if len(row_data) > 5 else 0)   # G
                        ad = clean_number(row_data[6].value if len(row_data) > 6 else 0)   # H
                        zustatek = clean_number(row_data[7].value if len(row_data) > 7 else 0)  # I
                        
                        if qty > 0 or name:
                            data.append({
                                "name": name,
                                "qty": qty,
                                "pct": pct,
                                "usd": usd,
                                "it": it,
                                "ad": ad,
                                "zustatek": zustatek
                            })
                            print(f"✅ {name}: qty={qty}, pct={pct}%")
                    except Exception as e:
                        print(f"Parse error for {name}: {e}")
                        continue
            
            print(f"✅ Got {len(data)} rows of data")
            return data if data else None
        else:
            return None
    except Exception as e:
        print(f"❌ Error reading sheets: {e}")
        import traceback
        traceback.print_exc()
        return None

def format_table(data):
    if not data:
        return "No data available"
    
    # Zkrácená verze bez %
    lines = []
    lines.append(f"{'Jmeno':<18} {'Qty':>6} {'USD':>14} {'IT':>12} {'AD':>12} {'Zůst':>12}")
    lines.append("-" * 85)
    
    for item in data:
        lines.append(f"{item['name'][:17]:<18} {item['qty']:>6.0f} {item['usd']:>13.0f} {item['it']:>11.0f} {item['ad']:>11.0f} {item['zustatek']:>11.0f}")
    
    total_qty = sum(d["qty"] for d in data)
    total_usd = sum(d["usd"] for d in data)
    total_it = sum(d["it"] for d in data)
    total_ad = sum(d["ad"] for d in data)
    total_zust = sum(d["zustatek"] for d in data)
    
    lines.append("-" * 85)
    lines.append(f"{'CELKEM':<18} {total_qty:>6.0f} {total_usd:>13.0f} {total_it:>11.0f} {total_ad:>11.0f} {total_zust:>11.0f}")
    
    return "\n".join(lines)

async def send_long_message(ctx, title, content):
    """Pošli dlouhou zprávu v několika blocích"""
    msg = f"```\n{content}\n```"
    
    if len(msg) <= 2000:
        await ctx.send(msg)
    else:
        # Rozděl na části
        await ctx.send(f"```\n{title}\n{content[:900]}...\n```")
        await ctx.send(f"```\n...{content[900:]}\n```")

@bot.command(name="capital")
async def capital_command(ctx):
    print("Command: !capital")
    data = get_capital_data()
    if data:
        table_text = format_table(data)
        await send_long_message(ctx, "KAPITAL CPD", table_text)
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
