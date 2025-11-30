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
SHEET_NAME = "Výplaty"

# Globální proměnné pro automatickou aktualizaci
message_ids = {}  # {f"{server_id}_{channel_id}": [main_msg_id, msg_id1, msg_id2, ...]}

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
    num = clean_number(value)
    return f"{int(num):,}".replace(',', '.')

def format_decimal(value):
    """Formátuj číslo na desetinná čísla s tečkou jako oddělovačem: 12,34 -> 12.34"""
    if not value:
        return "0.00"
    try:
        num = clean_number(value)
        return f"{num:.2f}"
    except:
        return "0.00"

def get_capital_data():
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        print(f"Opening sheet {SHEET_ID}...")
        sheet = client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
        print("✅ Sheet opened")
        
        # Čti sloupce B až I - řádky 3-33
        all_cells = sheet.range('B3:I33')
        print(f"✅ Got {len(all_cells)} cells")
        
        if len(all_cells) >= 8:
            data = []
            for i in range(0, len(all_cells), 8):  # 8 sloupců (B-I)
                row_data = all_cells[i:i+8]
                
                if len(row_data) >= 1 and row_data[0].value:
                    name = str(row_data[0].value).strip()
                    
                    # Přeskočit prázdné řádky, nadpisy a sumy
                    if not name or name.lower() in ['celkem', 'celk', 'suma', '', 'hráč'] or 'celkem' in name.lower():
                        continue
                    
                    try:
                        # B=name (index 0), E=podíl (index 3), H=splátka dluhu (index 6), I=K výplatě (index 7)
                        podil = row_data[3].value if len(row_data) > 3 else 0  # E - ponechej originální
                        splatka_dluhu = clean_number(row_data[6].value if len(row_data) > 6 else 0)  # H
                        k_vyplate = clean_number(row_data[7].value if len(row_data) > 7 else 0)  # I
                        
                        # Kontroluj jen číslo (splatka, vyplate) nebo samotný název
                        if splatka_dluhu > 0 or k_vyplate > 0 or name:
                            data.append({
                                "name": name,
                                "podil": podil,
                                "splatka_dluhu": splatka_dluhu,
                                "k_vyplate": k_vyplate
                            })
                            print(f"✅ {name}: podíl={podil}, splátka={splatka_dluhu}, k výplatě={k_vyplate}")
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
        return "Výplaty hráčů"
    elif part_num == 1:
        return "Výplaty hráčů (1. část)"
    elif part_num == 2:
        return "Výplaty hráčů (2. část)"
    else:
        return f"Výplaty hráčů ({part_num}. část)"

def create_embed(title, description, color, timestamp):
    """Vytvoří embed"""
    return discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=timestamp
    )

async def send_embeds(ctx, data):
    """Pošli data jako barevné Discord embeds"""
    if not data:
        await ctx.send("❌ Žádná data k zobrazení")
        return
    
    total_podil = sum(clean_number(d["podil"]) for d in data)
    total_splatka = sum(d["splatka_dluhu"] for d in data)
    total_vyplate = sum(d["k_vyplate"] for d in data)
    
    # Hlavní embed s totály
    main_embed = create_embed(
        "💰 Výplaty CZM8",
        "Přehled výplat hráčů",
        discord.Color.gold(),
        datetime.now()
    )
    
    main_embed.add_field(
        name="📊 Celkový Přehled",
        value=f"**Podíl:** `{format_decimal(total_podil)}`\n"
              f"**Splátka dluhu:** `{format_accounting(total_splatka)}`\n"
              f"**K výplatě:** `{format_accounting(total_vyplate)}`",
        inline=False
    )
    
    main_msg = await ctx.send(embed=main_embed)
    
    # Ulož ID hlavní zprávy
    key = f"{ctx.guild.id}_{ctx.channel.id}"
    message_ids[key] = [main_msg.id]
    
    # Divide data na stranky (po 9 hráčích na embed)
    chunk_size = 9
    total_chunks = (len(data) + chunk_size - 1) // chunk_size
    
    for chunk_idx in range(0, len(data), chunk_size):
        chunk = data[chunk_idx:chunk_idx + chunk_size]
        
        # Vytvoř embed pro tuto skupinu
        color = discord.Color.from_rgb(52, 211, 153) if chunk_idx == 0 else discord.Color.from_rgb(59, 130, 246)
        part_name = get_part_name(chunk_idx, chunk_size, total_chunks)
        
        embed = create_embed(
            f"👥 {part_name}",
            "",
            color,
            datetime.now()
        )
        
        # Přidej hráče do fieldu
        for item in chunk:
            podil_fmt = format_decimal(item['podil'])
            splatka_fmt = format_accounting(item['splatka_dluhu'])
            vyplate_fmt = format_accounting(item['k_vyplate'])
            
            value = (f"**Podíl:** {podil_fmt}\n"
                    f"**Splátka dluhu:** {splatka_fmt}\n"
                    f"**K výplatě:** {vyplate_fmt}")
            
            embed.add_field(
                name=f"🎮 {item['name']}",
                value=value,
                inline=True
            )
        
        msg = await ctx.send(embed=embed)
        message_ids[key].append(msg.id)

async def update_embeds(data):
    """Aktualizuj existující zprávy (bez smazání starých)"""
    if not data:
        print("❌ Žádná data k aktualizaci")
        return
    
    total_podil = sum(clean_number(d["podil"]) for d in data)
    total_splatka = sum(d["splatka_dluhu"] for d in data)
    total_vyplate = sum(d["k_vyplate"] for d in data)
    
    try:
        # Najdi kanál a zprávy
        guild = bot.get_guild(SERVER_ID)
        channel = guild.get_channel(CHANNEL_ID)
        
        if not channel:
            print("❌ Kanál nenalezen!")
            return
        
        key = f"{SERVER_ID}_{CHANNEL_ID}"
        
        if key not in message_ids or not message_ids[key]:
            print("⚠️ Zprávy ještě nebyly vytvořeny. Spusť !capital nejdříve.")
            return
        
        # Aktualizuj hlavní zprávu
        try:
            main_msg = await channel.fetch_message(message_ids[key][0])
            
            main_embed = create_embed(
                "💰 Výplaty CZM8",
                "Přehled výplat hráčů",
                discord.Color.gold(),
                datetime.now()
            )
            
            main_embed.add_field(
                name="📊 Celkový Přehled",
                value=f"**Podíl:** `{format_decimal(total_podil)}`\n"
                      f"**Splátka dluhu:** `{format_accounting(total_splatka)}`\n"
                      f"**K výplatě:** `{format_accounting(total_vyplate)}`",
                inline=False
            )
            
            await main_msg.edit(embed=main_embed)
            print("✅ Hlavní zpráva aktualizována")
        except Exception as e:
            print(f"❌ Chyba při aktualizaci hlavní zprávy: {e}")
        
        # Aktualizuj zprávy s hráči
        chunk_size = 9
        total_chunks = (len(data) + chunk_size - 1) // chunk_size
        
        for chunk_idx in range(0, len(data), chunk_size):
            chunk = data[chunk_idx:chunk_idx + chunk_size]
            msg_index = (chunk_idx // chunk_size) + 1
            
            if msg_index >= len(message_ids[key]):
                print(f"⚠️ Zpráva {msg_index} neexistuje")
                continue
            
            try:
                msg = await channel.fetch_message(message_ids[key][msg_index])
                
                color = discord.Color.from_rgb(52, 211, 153) if chunk_idx == 0 else discord.Color.from_rgb(59, 130, 246)
                part_name = get_part_name(chunk_idx, chunk_size, total_chunks)
                
                embed = create_embed(
                    f"👥 {part_name}",
                    "",
                    color,
                    datetime.now()
                )
                
                for item in chunk:
                    podil_fmt = format_decimal(item['podil'])
                    splatka_fmt = format_accounting(item['splatka_dluhu'])
                    vyplate_fmt = format_accounting(item['k_vyplate'])
                    
                    value = (f"**Podíl:** {podil_fmt}\n"
                            f"**Splátka dluhu:** {splatka_fmt}\n"
                            f"**K výplatě:** {vyplate_fmt}")
                    
                    embed.add_field(
                        name=f"🎮 {item['name']}",
                        value=value,
                        inline=True
                    )
                
                await msg.edit(embed=embed)
                print(f"✅ Zpráva {msg_index} aktualizována")
            except Exception as e:
                print(f"❌ Chyba při aktualizaci zprávy {msg_index}: {e}")
    
    except Exception as e:
        print(f"❌ Chyba při aktualizaci: {e}")

@tasks.loop(minutes=30)
async def auto_update():
    """Automaticky aktualizuj zprávy každých 30 minut"""
    print("\n🔄 Automatická aktualizace...")
    data = get_capital_data()
    if data:
        await update_embeds(data)
    else:
        print("❌ Nelze přečíst data z Google Sheets")

@auto_update.before_loop
async def before_auto_update():
    """Čekej než je bot připraven"""
    await bot.wait_until_ready()

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
    
    # Spusť automatickou aktualizaci
    if not auto_update.is_running():
        auto_update.start()
        print("🔄 Automatická aktualizace spuštěna (každých 30 minut)")

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
