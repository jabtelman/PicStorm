import discord
import asyncio
import aiohttp
import random
import json
import logging
from discord.ext import commands
from discord import app_commands


# === НАСТРОЙКА ЛОГИРОВАНИЯ ===
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", filename="bot.log", filemode="a")

# === ЗАГРУЗКА И СОХРАНЕНИЕ НАСТРОЕК ===
CONFIG_FILE = "config.json"

def load_config():
    """Загружает конфигурацию из JSON."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        logging.warning("⚠️ Файл конфигурации не найден или поврежден. Создаю новый...")
        return {
            "DISCORD_TOKEN": "",
            "IMGUR_CLIENT_ID": "",
            "CHANNELS": [],
            "SEND_INTERVAL": 60,
            "SEARCH_TOPIC": "memes"
        }

def save_config():
    """Сохраняет конфигурацию в JSON."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

config = load_config()

# === ПЕРЕМЕННЫЕ ===
DISCORD_TOKEN = config["DISCORD_TOKEN"]
IMGUR_CLIENT_ID = config["IMGUR_CLIENT_ID"]
CHANNELS = config["CHANNELS"]
SEND_INTERVAL = config["SEND_INTERVAL"]
SEARCH_TOPIC = config["SEARCH_TOPIC"]
SENT_IMAGES = set()  # Кэш уже отправленных картинок

# === ФУНКЦИИ РАБОТЫ С КЭШЕМ ===
def load_cache():
    """Загружает кэш отправленных картинок из файла."""
    global SENT_IMAGES
    try:
        with open("sent_images.json", "r", encoding="utf-8") as file:
            SENT_IMAGES = set(json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        SENT_IMAGES = set()

def save_cache():
    """Сохраняет кэш отправленных картинок в файл."""
    with open("sent_images.json", "w", encoding="utf-8") as file:
        json.dump(list(SENT_IMAGES), file, indent=4)

load_cache()  # Загружаем кеш при старте

# === НАСТРОЙКА БОТА ===
intents = discord.Intents.default()
intents.message_content = True  # Включаем получение сообщений
intents.presences = True  # Если понадобится (например, для статусов пользователей)
intents.members = True  # Если бот работает с участниками сервера

bot = commands.Bot(command_prefix="!", intents=intents)

# === ФУНКЦИИ ===
async def get_imgur_image():
    """Ищет случайный мем по тегу в Imgur API."""
    url = f"https://api.imgur.com/3/gallery/search/?q={SEARCH_TOPIC}"
    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                images = [item["link"] for item in data["data"] if "link" in item and item["link"].startswith("https")]

                available_images = list(set(images) - SENT_IMAGES)
                if available_images:
                    image = random.choice(available_images)
                    SENT_IMAGES.add(image)
                    return image
                return random.choice(images) if images else None
            else:
                logging.error(f"Ошибка запроса к Imgur: {response.status}")
                return None

async def send_funny_images():
    """Циклическая отправка мемов."""
    await bot.wait_until_ready()

    while not bot.is_closed():
        for channel_id in CHANNELS:
            channel = bot.get_channel(channel_id)
            if channel:
                image_url = await get_imgur_image()
                if image_url:
                    await channel.send(image_url)
                else:
                    logging.warning("Не удалось найти картинку.")
        await asyncio.sleep(SEND_INTERVAL)

# === КОМАНДЫ ===

@bot.tree.command(name="help", description="Показывает список команд")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="📜 Команды бота", color=discord.Color.blue())
    embed.add_field(name="/help", value="Показывает этот список", inline=False)
    embed.add_field(name="/mem", value="Отправляет случайный мем", inline=False)
    embed.add_field(name="/set_topic [тема]", value="Меняет тему поиска мемов", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.command(name="set_topic")
async def set_topic(ctx, *, topic: str):
    """Задает новую тематику поиска изображений."""
    global SEARCH_TOPIC
    SEARCH_TOPIC = topic
    config["SEARCH_TOPIC"] = topic
    save_config()
    await ctx.send(f"🔍 Тематика изображений изменена на: **{topic}**")

@bot.command(name="set_interval")
async def set_interval(ctx, seconds: int):
    """Задает новый интервал отправки изображений."""
    global SEND_INTERVAL
    if seconds < 10:
        await ctx.send("⏳ Интервал не может быть меньше 10 секунд!")
        return
    SEND_INTERVAL = seconds
    config["SEND_INTERVAL"] = seconds
    save_config()
    await ctx.send(f"⏰ Интервал отправки изображений изменен на **{seconds}** секунд.")

@bot.command(name="show_topic")
async def show_topic(ctx):
    """Показывает нынешнюю тему."""
    await ctx.send(f"🔍 Нынешняя тема: **{SEARCH_TOPIC}**")

@bot.command(name="show_interval")
async def show_interval(ctx):
    """Показывает заданный интервал."""
    await ctx.send(f"⏰ Сейчас задан следующий временной интервал: **{SEND_INTERVAL}** секунд")

@bot.command(name="send_mem")
async def send_mem(ctx):
    """Отправляет случайный мем по запросу."""
    image_url = await get_imgur_image()
    if image_url:
        await ctx.send(f"Вот тебе мем:\n{image_url}")
    else:
        await ctx.send("😕 Не удалось найти мем.")

@bot.event
async def on_ready():
    logging.info(f"✅ Бот {bot.user} запущен!")

    # Синхронизация команд
    try:
        synced = await bot.tree.sync()
        logging.info(f"📌 Синхронизированы {len(synced)} команд.")
    except Exception as e:
        logging.error(f"❌ Ошибка синхронизации команд: {e}")

    bot.loop.create_task(send_funny_images())

bot.run(DISCORD_TOKEN)