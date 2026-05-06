import discord
from discord.ext import commands, tasks
import motor.motor_asyncio
import os
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread

# ══════════════════════════════════════════
#              CẤU HÌNH / CONFIG
# ══════════════════════════════════════════
TOKEN      = os.environ.get("DISCORD_TOKEN_CAL")
MONGO_URL  = os.environ.get("MONGO_URL")
CHANNEL_ID = 1488413245931917395  # Kênh thông báo

# ══════════════════════════════════════════
#           KẾT NỐI DATABASE
# ══════════════════════════════════════════
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(
    MONGO_URL,
    serverSelectionTimeoutMS=5000,
    tlsInsecure=True
)
db       = mongo_client["WorldRP_2000"]
cal_col  = db["WorldCalendar"]  # Lưu ngày hiện tại của world

# ══════════════════════════════════════════
#           HÀM TÍNH NGÀY WORLD
# ══════════════════════════════════════════
MONTHS_VI = [
    "", "Tháng 1", "Tháng 2", "Tháng 3", "Tháng 4",
    "Tháng 5", "Tháng 6", "Tháng 7", "Tháng 8",
    "Tháng 9", "Tháng 10", "Tháng 11", "Tháng 12"
]
MONTHS_EN = [
    "", "January", "February", "March", "April",
    "May", "June", "July", "August", "September",
    "October", "November", "December"
]
SEASON_VI = {
    1: "❄️ Mùa đông", 2: "❄️ Mùa đông", 3: "🌸 Mùa xuân",
    4: "🌸 Mùa xuân", 5: "🌸 Mùa xuân", 6: "☀️ Mùa hè",
    7: "☀️ Mùa hè",   8: "☀️ Mùa hè",   9: "🍂 Mùa thu",
    10: "🍂 Mùa thu", 11: "🍂 Mùa thu", 12: "❄️ Mùa đông"
}

async def get_world_date():
    """Lấy ngày hiện tại của world từ DB"""
    doc = await cal_col.find_one({"_id": "world_date"})
    if not doc:
        # Mặc định: 3/5/1965
        await cal_col.insert_one({
            "_id": "world_date",
            "day": 3, "month": 5, "year": 1965
        })
        return {"day": 3, "month": 5, "year": 1965}
    return doc

async def advance_world_date():
    """Tiến thêm 2 tháng mỗi ngày thực tế"""
    doc = await get_world_date()
    day   = doc["day"]
    month = doc["month"] + 2
    year  = doc["year"]

    if month > 12:
        month -= 12
        year  += 1

    await cal_col.update_one(
        {"_id": "world_date"},
        {"$set": {"day": day, "month": month, "year": year}},
        upsert=True
    )
    return {"day": day, "month": month, "year": year}

def format_date(d):
    day   = d["day"]
    month = d["month"]
    year  = d["year"]
    return {
        "vi": f"Ngày {day} {MONTHS_VI[month]} năm {year}",
        "en": f"{MONTHS_EN[month]} {day}, {year}",
        "season": SEASON_VI.get(month, ""),
        "day": day, "month": month, "year": year
    }

# ══════════════════════════════════════════
#              KHỞI TẠO BOT
# ══════════════════════════════════════════
class CalBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.daily_announcement.start()
        print("✅ Calendar Bot sẵn sàng / Ready!")

    @tasks.loop(minutes=1)
    async def daily_announcement(self):
        # Kiểm tra giờ Việt Nam (UTC+7) = 6:00 sáng
        now_vn = datetime.now(timezone(timedelta(hours=7)))
        if now_vn.hour == 6 and now_vn.minute == 0:
            await self.send_daily(advance=True)

    async def send_daily(self, advance=True):
        channel = self.get_channel(CHANNEL_ID)
        if not channel:
            print(f"❌ Không tìm thấy channel {CHANNEL_ID}")
            return

        if advance:
            date = await advance_world_date()
        else:
            date = await get_world_date()

        d = format_date(date)

        embed = discord.Embed(
            title="📅 THÔNG BÁO NGÀY MỚI  ·  New Day Announcement",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="🇻🇳 Ngày trong World  ·  🇬🇧 World Date",
            value=f"```\n{d['vi']}\n{d['en']}\n```",
            inline=False
        )
        embed.add_field(name="🌍 Mùa  ·  Season", value=d["season"], inline=True)
        embed.add_field(
            name="📆 Thực tế  ·  Real Date",
            value=f"<t:{int(datetime.now().timestamp())}:D>",
            inline=True
        )
        embed.set_footer(text="WorldRP 1960s  ·  Mỗi ngày thực = 2 tháng trong world")
        embed.timestamp = datetime.utcnow()

        await channel.send(embed=embed)

bot = CalBot()

# ══════════════════════════════════════════
#                  LỆNH SLASH
# ══════════════════════════════════════════

@bot.command()
async def sync(ctx):
    if ctx.author.guild_permissions.administrator:
        fmt = await bot.tree.sync()
        await ctx.send(f"✅ Synced {len(fmt)} commands!")

# Xem ngày hiện tại
@bot.tree.command(name="ngay_hientai", description="📅 Xem ngày hiện tại của World / View current world date")
async def ngay_hientai(interaction: discord.Interaction):
    try:
        await interaction.response.defer()
    except:
        return

    date = await get_world_date()
    d = format_date(date)

    embed = discord.Embed(
        title="📅 NGÀY HIỆN TẠI  ·  Current World Date",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="🇻🇳 Ngày trong World",
        value=f"**{d['vi']}**",
        inline=False
    )
    embed.add_field(
        name="🇬🇧 World Date",
        value=f"**{d['en']}**",
        inline=False
    )
    embed.add_field(name="🌍 Mùa  ·  Season", value=d["season"], inline=True)
    embed.set_footer(text="WorldRP 1960s  ·  Mỗi ngày thực = 2 tháng trong world")
    embed.timestamp = datetime.utcnow()
    await interaction.followup.send(embed=embed)

# Set ngày thủ công (Admin)
@bot.tree.command(name="set_ngay", description="[ADMIN] Set ngày trong world / Set world date")
@discord.app_commands.describe(ngay="Ngày / Day", thang="Tháng / Month", nam="Năm / Year")
async def set_ngay(interaction: discord.Interaction, ngay: int, thang: int, nam: int):
    try:
        await interaction.response.defer()
    except:
        return

    if not interaction.user.guild_permissions.administrator:
        return await interaction.followup.send("❌ Chỉ Admin mới dùng được! / Admin only!")

    if not (1 <= ngay <= 31 and 1 <= thang <= 12 and nam > 0):
        return await interaction.followup.send("❌ Ngày tháng năm không hợp lệ! / Invalid date!")

    await cal_col.update_one(
        {"_id": "world_date"},
        {"$set": {"day": ngay, "month": thang, "year": nam}},
        upsert=True
    )

    d = format_date({"day": ngay, "month": thang, "year": nam})
    embed = discord.Embed(
        title="✅ ĐÃ SET NGÀY  ·  Date Updated",
        color=discord.Color.green()
    )
    embed.add_field(name="🇻🇳 Ngày mới", value=f"**{d['vi']}**", inline=False)
    embed.add_field(name="🇬🇧 New Date", value=f"**{d['en']}**", inline=False)
    embed.set_footer(text=f"Set bởi / by: {interaction.user.name}")
    embed.timestamp = datetime.utcnow()
    await interaction.followup.send(embed=embed)

# Test gửi thông báo ngay (Admin)
@bot.tree.command(name="test_thongbao", description="[ADMIN] Test gửi thông báo ngay / Test announcement")
async def test_thongbao(interaction: discord.Interaction):
    try:
        await interaction.response.defer(ephemeral=True)
    except:
        return

    if not interaction.user.guild_permissions.administrator:
        return await interaction.followup.send("❌ Admin only!")

    await bot.send_daily(advance=False)
    await interaction.followup.send("✅ Đã gửi thông báo test! / Test sent!")

# ══════════════════════════════════════════
#       KEEP-ALIVE + CHẠY BOT
# ══════════════════════════════════════════
flask_app = Flask("")

@flask_app.route("/")
def home():
    return "📅 Calendar Bot đang chạy! / Running!", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=8080)

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    print("📅 Flask keep-alive started!")
    bot.run(TOKEN)
