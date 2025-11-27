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
print("CAPITAL BOT - CZM8")
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
        
        # Čti sloupce B, D, E, I - řádky 3-30
        # B=Jméno, D=Akcie, E=%, I=Nárok
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
                        # B=name, D=akcie, E=pct, I=narok
                        akcie = clean_number(row_data[2].value if len(row_data) > 2 else 0)  # D
                        pct = clean_number(row_data[3].value if len(row_data) > 3 else 0)  # E
                        narok = clean_number(row_data[7].value if len(row_data) > 7 else 0)  # I
                        
                        if akcie > 0 or name:
                            data.append({
                                "name": name,
                                "akcie": akcie,
                                "pct": pct,
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

def get_part_name(chunk_idx, chunk_size, total_chunks):
    """Vrátí název části (1. část), (2. část), atd."""
    part_num = (chunk_idx // chunk_size) + 1
    if total_chunks == 1:
        return "Členové"
    elif part_num == 1:
        return "Členové (1. část)"
    elif part_num == 2:
        return "Členové (2. část)"
    else:
        return f"Členové ({part_num}. část)"

async def send_embeds(ctx, data):
    """Pošli data jako barevné Discord embeds"""
    if not data:
        await ctx.send("❌ Žádná data k zobrazení")
        return
    
    total_akcie = sum(d["akcie"] for d in data)
    total_pct = sum(d["pct"] for d in data)
    total_narok = sum(d["narok"] for d in data)
    
    # Hlavní embed s totály
    main_embed = discord.Embed(
        title="💰 Kapitál CZM8",
        description="Přehled majetku hráčů",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    
    main_embed.add_field(
        name="📊 Celkový Přehled",
        value=f"**Akcie:** `{total_akcie:,.0f}`\n"
              f"**%:** `{total_pct:,.1f}`\n"
              f"**Nárok:** `{format_accounting(total_narok)}`",
        inline=False
    )
    
    await ctx.send(embed=main_embed)
    
    # Divide data na stranky (po 9 hráčích na embed)
    chunk_size = 9
    total_chunks = (len(data) + chunk_size - 1) // chunk_size
    
    for chunk_idx in range(0, len(data), chunk_size):
        chunk = data[chunk_idx:chunk_idx + chunk_size]
        
        # Vytvoř embed pro tuto skupinu
        color = discord.Color.from_rgb(52, 211, 153) if chunk_idx == 0 else discord.Color.from_rgb(59, 130, 246)
        part_name = get_part_name(chunk_idx, chunk_size, total_chunks)
        
        embed = discord.Embed(
            title=f"👥 {part_name}",
            color=color,
            timestamp=datetime.now()
        )
        
        # Přidej hráče do fieldu
        for item in chunk:
            narok_fmt = format_accounting(item['narok'])
            
            value = (f"**Akcie:** {item['akcie']:.0f}\n"
                    f"**%:** {item['pct']:.2f}\n"
                    f"**Nárok:** {narok_fmt}")
            
            embed.add_field(
                name=f"🎮 {item['name']}",
                value=value,
                inline=True
            )
        
        await ctx.send(embed=embed)

@bot.command(name="capital")
async def capital_command(ctx):
    print("Command: !capital")
    data = get_capital_data()
    if data:
        await send_embeds(ctx, data)
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
