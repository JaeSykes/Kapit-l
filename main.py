import discord
from discord.ext import commands, tasks
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# CAPITAL BOT - L2REBORN CPD (FINÁLNÍ VERZE)
# Čte konkrétní rozsah: řádky 4-21, sloupce B-I
# List: "Kapitál new"
# ═══════════════════════════════════════════════════════════════

# Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Konfigurace
SERVER_ID = int(os.getenv("GUILD_ID", "1397286059406000249"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "1443610848391204955"))
SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
MESSAGE_IDS_FILE = "capital_message_ids.json"
UPDATE_INTERVAL = 3  # minuty

print("="*60)
print("🚀 CAPITAL BOT - Inicializace (Finální verze)")
print("="*60)

# ═══════════════════════════════════════════════════════════════
# GOOGLE SHEETS
# ═══════════════════════════════════════════════════════════════

def get_sheets_client():
    """Připojení k Google Sheets"""
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

def get_capital_data():
    """Čtení dat z konkrétního rozsahu Google Sheets"""
    try:
        client = get_sheets_client()
        if not client:
            return None
        
        sheet = client.open_by_key(SHEET_ID).worksheet("Kapitál new")
        
        # Čtení rozsahu: B4:I21 (hráči bez headeru)
        rows = sheet.range('B4:I21')
        
        if not rows:
            print("⚠️  Rozsah je prázdný")
            return None
        
        data = []
        
        # Konverze z range() na řádky
        for i in range(0, len(rows), 8):  # 8 sloupců (B-I)
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
                    
                    if qty > 0:  # Jen hráče s qty > 0
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
        print(f"❌ Chyba při čtení Sheets: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
# FORMÁTOVÁNÍ TABULKY
# ═══════════════════════════════════════════════════════════════

def create_capital_table(data):
    """Vytvoření úplné tabulky jako text"""
    if not data:
        return "``````"
    
    # Header
    table = "```
    table += "📊 KAPITÁL CP - ÚPLNÝ PŘEHLED\n"
    table += "═" * 135 + "\n"
    table += f"{'Jméno':<20} │ {'Qty':>8} │ {'%':>7} │ {'$ (Aden)':>16} │ {'-it (K)':>12} │ {'-ad (K)':>12} │ {'= (Zůst.)':>16}\n"
    table += "─" * 135 + "\n"
    
    # Data řádky
    for item in data:
        name_fmt = item["name"][:19].ljust(20)
        qty_fmt = f"{item['qty']:>8.0f}"
        pct_fmt = f"{item['pct']:>6.2f}%"
        usd_fmt = f"{item['usd']:>15.0f}"
        it_fmt = f"{item['it']:>11.0f}"
        ad_fmt = f"{item['ad']:>11.0f}"
        zust_fmt = f"{item['zustatek']:>15.0f}"
        
        table += f"{name_fmt} │ {qty_fmt} │ {pct_fmt} │ {usd_fmt} │ {it_fmt} │ {ad_fmt} │ {zust_fmt}\n"
    
    # Total řádek
    total_qty = sum(d["qty"] for d in data)
    total_pct = sum(d["pct"] for d in data)
    total_usd = sum(d["usd"] for d in data)
    total_it = sum(d["it"] for d in data)
    total_ad = sum(d["ad"] for d in data)
    total_zust = sum(d["zustatek"] for d in data)
    
    table += "─" * 135 + "\n"
    table += f"{'CELKEM':<20} │ {total_qty:>8.0f} │ {total_pct:>6.2f}% │ {total_usd:>15.0f} │ {total_it:>11.0f} │ {total_ad:>11.0f} │ {total_zust:>15.0f}\n"
    table += "═" * 135 + "\n"
    table += f"🔄 Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    table += "```"
    
    return table

# ═══════════════════════════════════════════════════════════════
# SPRÁVA ZPRÁV
# ═══════════════════════════════════════════════════════════════

def load_message_ids():
    """Načtení uložených ID zpráv"""
    if os.path.exists(MESSAGE_IDS_FILE):
        try:
            with open(MESSAGE_IDS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"capital_message": None}

def save_message_ids(msg_ids):
    """Uložení ID zpráv"""
    with open(MESSAGE_IDS_FILE, "w", encoding="utf-8") as f:
        json.dump(msg_ids, f, ensure_ascii=False, indent=2)

async def update_capital_display():
    """Aktualizace kapitál zprávy"""
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
                print(f"✅ Kapitál zpráva aktualizována: {datetime.now().strftime('%H:%M:%S')}")
                return
            except Exception as e:
                print(f"⚠️  Starou zprávu nelze najít: {e}")
                msg_ids["capital_message"] = None
        
        # Pokud zpráva neexistuje, vytvoř novou
        msg = await channel.send(table_text)
        msg_ids["capital_message"] = str(msg.id)
        save_message_ids(msg_ids)
        print(f"✅ Nová kapitál zpráva vytvořena: {msg.id}")
        
    except Exception as e:
        print(f"❌ Chyba při aktualizaci: {e}")

# ═══════════════════════════════════════════════════════════════
# BACKGROUND TASK
# ═══════════════════════════════════════════════════════════════

@tasks.loop(minutes=UPDATE_INTERVAL)
async def update_capital_task():
    """Periodická aktualizace kapitálu"""
    await update_capital_display()

@update_capital_task.before_loop
async def before_update_task():
    """Čekání na připravení bota"""
    await bot.wait_until_ready()

# ═══════════════════════════════════════════════════════════════
# PŘÍKAZY
# ═══════════════════════════════════════════════════════════════

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
    """Poslat novou kapitál zprávu do kanálu (Admin only)"""
    data = get_capital_data()
    table_text = create_capital_table(data)
    msg = await ctx.send(table_text)
    
    msg_ids = load_message_ids()
    msg_ids["capital_message"] = str(msg.id)
    save_message_ids(msg_ids)
    
    await ctx.send("✅ Nová kapitál zpráva nastavena!", ephemeral=True)

# ═══════════════════════════════════════════════════════════════
# SPUŠTĚNÍ
# ═══════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    """Bot je připraven"""
    print("="*60)
    print(f"✅ Bot je online jako {bot.user}")
    print("="*60)
    
    guild = bot.get_guild(SERVER_ID)
    if guild:
        print(f"✅ Server: {guild.name} ({SERVER_ID})")
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            print(f"✅ Kanál: {channel.name} ({CHANNEL_ID})")
            print(f"✅ Update interval: {UPDATE_INTERVAL} minut")
            print(f"✅ List: 'Kapitál new'")
            print(f"✅ Rozsah: B4:I21")
            
            # První update
            await update_capital_display()
            
            # Spusť background task
            if not update_capital_task.is_running():
                update_capital_task.start()
                print("✅ Background task spuštěn!")
            
            print("="*60)
            print("✅ CAPITAL BOT JE PŘIPRAVEN!")
            print("="*60)
        else:
            print(f"❌ Kanál {CHANNEL_ID} nenalezen!")
    else:
        print(f"❌ Server {SERVER_ID} nenalezen!")

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("❌ DISCORD_TOKEN není nastaven v .env!")
