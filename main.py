import discord
from discord.ext import commands, tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
from datetime import datetime

# Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Konfigurace
SERVER_ID = int(os.getenv("GUILD_ID", "1397286059406000249"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "1443362011957170216"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
MESSAGE_IDS_FILE = "capital_message_ids.json"
UPDATE_INTERVAL = 3  # minuty

# Google Sheets setup
def get_sheets_client():
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        creds_dict = json.loads(creds_json)
        scope = ["https://spreadsheets.google.com/auth/spreadsheets"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        print(f"❌ Chyba při připojení k Google Sheets: {e}")
        return None

# Načtení ID zpráv
def load_message_ids():
    if os.path.exists(MESSAGE_IDS_FILE):
        try:
            with open(MESSAGE_IDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"capital_message": None}

# Uložení ID zpráv
def save_message_ids(msg_ids):
    with open(MESSAGE_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(msg_ids, f, ensure_ascii=False, indent=2)

# Čtení dat z Google Sheets
def get_capital_data():
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        sheet = client.open_by_key(SHEET_ID).sheet1
        rows = sheet.get_all_values()
        
        if len(rows) < 2:
            return None
        
        # Přeskočit header (řádek 0)
        data = []
        for row in rows[1:]:
            if len(row) >= 8 and row[0].strip():
                try:
                    name = row[0].strip()
                    qty = float(row[1].replace(",", ".")) if len(row) > 1 else 0
                    pct = float(row[2].replace(",", ".")) if len(row) > 2 else 0
                    usd = float(row[3].replace(",", ".")) if len(row) > 3 else 0
                    it = float(row[4].replace(",", ".")) if len(row) > 4 else 0
                    ad = float(row[5].replace(",", ".")) if len(row) > 5 else 0
                    zustatek = float(row[6].replace(",", ".")) if len(row) > 6 else 0
                    
                    data.append({
                        "name": name,
                        "qty": qty,
                        "pct": pct,
                        "usd": usd,
                        "it": it,
                        "ad": ad,
                        "zustatek": zustatek
                    })
                except:
                    continue
        
        return data
    except Exception as e:
        print(f"❌ Chyba při čtení Sheets: {e}")
        return None

# Vytvoření tabulky jako text
def create_capital_table(data):
    if not data:
        return "``````"
    
    # Filtruj jen řádky kde je qty > 0
    data_filtered = [d for d in data if d["qty"] > 0]
    
    # Header
    table = "```
    table += "📊 KAPITÁL CPD - ÚPLNÝ PŘEHLED\n"
    table += "═" * 130 + "\n"
    table += f"{'Jméno':<20} │ {'Qty':>8} │ {'%':>7} │ {'$ (Aden)':>16} │ {'-it (K)':>12} │ {'-ad (K)':>12} │ {'= (Zůst.)':>16}\n"
    table += "─" * 130 + "\n"
    
    # Data řádky
    for item in data_filtered:
        name_fmt = item["name"][:19].ljust(20)
        qty_fmt = f"{item['qty']:>8.0f}"
        pct_fmt = f"{item['pct']:>6.2f}%"
        usd_fmt = f"{item['usd']:>15.0f}"
        it_fmt = f"{item['it']:>11.0f}"
        ad_fmt = f"{item['ad']:>11.0f}"
        zust_fmt = f"{item['zustatek']:>15.0f}"
        
        table += f"{name_fmt} │ {qty_fmt} │ {pct_fmt} │ {usd_fmt} │ {it_fmt} │ {ad_fmt} │ {zust_fmt}\n"
    
    # Total řádek
    total_qty = sum(d["qty"] for d in data_filtered)
    total_pct = sum(d["pct"] for d in data_filtered)
    total_usd = sum(d["usd"] for d in data_filtered)
    total_it = sum(d["it"] for d in data_filtered)
    total_ad = sum(d["ad"] for d in data_filtered)
    total_zust = sum(d["zustatek"] for d in data_filtered)
    
    table += "─" * 130 + "\n"
    table += f"{'CELKEM':<20} │ {total_qty:>8.0f} │ {total_pct:>6.2f}% │ {total_usd:>15.0f} │ {total_it:>11.0f} │ {total_ad:>11.0f} │ {total_zust:>15.0f}\n"
    table += "═" * 130 + "\n"
    table += f"Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    table += "```"
    
    return table

# Aktualizace zprávy
async def update_capital_display():
    try:
        channel = bot.get_channel(CHANNEL_ID)
        guild = bot.get_guild(SERVER_ID)
        
        if not channel or not guild:
            print("❌ Kanál nebo server nenalezen")
            return
        
        data = get_capital_data()
        table_text = create_capital_table(data)
        
        msg_ids = load_message_ids()
        
        # Pokud zpráva existuje, uprav ji
        if msg_ids["capital_message"]:
            try:
                msg = await channel.fetch_message(int(msg_ids["capital_message"]))
                await msg.edit(content=table_text)
                print(f"✅ Kapitál zpráva aktualizována: {datetime.now()}")
                return
            except Exception as e:
                print(f"⚠️ Chyba při editaci zprávy: {e}")
                msg_ids["capital_message"] = None
        
        # Pokud zpráva neexistuje, vytvoř novou
        msg = await channel.send(table_text)
        msg_ids["capital_message"] = str(msg.id)
        save_message_ids(msg_ids)
        print(f"✅ Nová kapitál zpráva vytvořena: {msg.id}")
        
    except Exception as e:
        print(f"❌ Chyba při aktualizaci: {e}")

# Background task - periodicka aktualizace
@tasks.loop(minutes=UPDATE_INTERVAL)
async def update_capital_task():
    await update_capital_display()

@update_capital_task.before_loop
async def before_update_task():
    await bot.wait_until_ready()

# Příkazy
@bot.command(name="capital")
async def capital_command(ctx):
    """Zobrazit aktuální kapitál"""
    data = get_capital_data()
    table_text = create_capital_table(data)
    await ctx.send(table_text)

@bot.command(name="capital-refresh")
@commands.has_permissions(administrator=True)
async def capital_refresh(ctx):
    """Manuálně aktualizovat kapitál (Admin only)"""
    await update_capital_display()
    await ctx.send("✅ Kapitál byl aktualizován!", ephemeral=True)

@bot.command(name="capital-pin")
@commands.has_permissions(administrator=True)
async def capital_pin(ctx):
    """Poslat novou kapitál zprávu do kanálu"""
    data = get_capital_data()
    table_text = create_capital_table(data)
    msg = await ctx.send(table_text)
    
    msg_ids = load_message_ids()
    msg_ids["capital_message"] = str(msg.id)
    save_message_ids(msg_ids)
    
    await ctx.send("✅ Kapitál zpráva nastavena!", ephemeral=True)

# Spuštění
@bot.event
async def on_ready():
    print(f"✅ Bot je online jako {bot.user}")
    guild = bot.get_guild(SERVER_ID)
    if guild:
        print(f"✅ Server: {guild.name}")
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            print(f"✅ Kanál: {channel.name}")
            # První update
            await update_capital_display()
            # Spusť background task
            update_capital_task.start()
            print("✅ Kapitál bot je připraven!")

token = os.getenv("DISCORD_TOKEN")
bot.run(token)
