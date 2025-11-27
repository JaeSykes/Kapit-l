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

def format_accounting(value):
    """Formátuj číslo v účetním formátu: 10000 -> 10.000"""
    return f"{int(value):,}".replace(',', '.')

def get_capital_data():
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        print(f"Opening sheet {SHEET_ID}...")
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        print("✅ Sheet opened")
        
        # Čti sloupce B-I (bez C), řádky 3-30
        # B=Jméno, D=Akcie, E=%, F=CASH, G=itemy, H=Adeny, I=Nárok
        all_cells = sheet.range('B3:I30')
        print(f"✅ Got {len(all_cells)} cells")
        
        if len(all_cells) >= 8:
            data = []
            for i in range(0, len(all_cells), 8):  # 8 sloupců (B-I)
                row_data = all_cells[i:i+8]
                
                if len(row_data) >= 1 and row_data[0].value:
                    name = str(row_data[0].value).strip()
                    
                    # Přeskočit prázdné řádky, nadpisy a sumy
                    if not name or name.lower() in ['celkem', 'celk', 'suma', '', 'jmeno'] or 'celkem' in name.lower():
                        continue
                    
                    try:
                        # B=name, C=skip, D=akcie, E=pct, F=cash, G=itemy, H=adeny, I=narok
                        akcie = clean_number(row_data[2].value if len(row_data) > 2 else 0)  # D
                        pct = clean_number(row_data[3].value if len(row_data) > 3 else 0)  # E
                        cash = clean_number(row_data[4].value if len(row_data) > 4 else 0)  # F
                        itemy = clean_number(row_data[5].value if len(row_data) > 5 else 0)   # G
                        adeny = clean_number(row_data[6].value if len(row_data) > 6 else 0)   # H
                        narok = clean_number(row_data[7].value if len(row_data) > 7 else 0)  # I
                        
                        if akcie > 0 or name:
                            data.append({
                                "name": name,
                                "akcie": akcie,
                                "pct": pct,
                                "cash": cash,
                                "itemy": itemy,
                                "adeny": adeny,
                                "narok": narok
                            })
                            print(f"✅ {name}: akcie={akcie}, pct={pct}%")
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
    """Formatuj tabulku pro zobrazení"""
    if not data:
        return "No data available"
    
    lines = []
    lines.append(f"{'Jmeno':<18} {'Akcie':>6} {'CASH':>14} {'itemy':>12} {'Adeny':>12} {'Nárok':>12}")
    lines.append("-" * 85)
    
    for item in data:
        # Formátuj CASH a Nárok v účetním formátu (tisícioddělovač)
        cash_fmt = format_accounting(item['cash'])
        narok_fmt = format_accounting(item['narok'])
        
        # Formátuj itemy a Adeny v záporném účetním formátu
        itemy_fmt = f"-{format_accounting(item['itemy'])}" if item['itemy'] > 0 else "0"
        adeny_fmt = f"-{format_accounting(item['adeny'])}" if item['adeny'] > 0 else "0"
        
        lines.append(f"{item['name'][:17]:<18} {item['akcie']:>6.0f} {cash_fmt:>14} {itemy_fmt:>12} {adeny_fmt:>12} {narok_fmt:>12}")
    
    total_akcie = sum(d["akcie"] for d in data)
    total_cash = sum(d["cash"] for d in data)
    total_itemy = sum(d["itemy"] for d in data)
    total_adeny = sum(d["adeny"] for d in data)
    total_narok = sum(d["narok"] for d in data)
    
    # Formátuj totály
    total_cash_fmt = format_accounting(total_cash)
    total_narok_fmt = format_accounting(total_narok)
    total_itemy_fmt = f"-{format_accounting(total_itemy)}" if total_itemy > 0 else "0"
    total_adeny_fmt = f"-{format_accounting(total_adeny)}" if total_adeny > 0 else "0"
    
    lines.append("-" * 85)
    lines.append(f"{'CELKEM':<18} {total_akcie:>6.0f} {total_cash_fmt:>14} {total_itemy_fmt:>12} {total_adeny_fmt:>12} {total_narok_fmt:>12}")
    
    return "\n".join(lines)

@bot.command(name="capital")
async def capital_command(ctx):
    print("Command: !capital")
    data = get_capital_data()
    if data:
        # Vytvoř embed
        embed = discord.Embed(
            title="💰 KAPITAL CPD",
            description="Přehled majetku hráčů",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        # Formatuj tabulku
        table_text = format_table(data)
        
        # Přidej tabulku do embedu jako code block
        embed.add_field(
            name="📊 Detailní Přehled",
            value=f"```\n{table_text}\n```",
            inline=False
        )
        
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Nemohu přečíst data z Google Sheets")

@bot.command(name="test")
async def test(ctx):
    embed = discord.Embed(
        title="✅ Bot Funguje",
        description="Správkyně kapitálu je online!",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

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
