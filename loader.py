from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from handlers.user_handler import router
from dotenv import load_dotenv, find_dotenv
import os
import logging
import sys


WEB_SERVER_HOST = "::"
WEB_SERVER_PORT = 8443
WEBHOOK_PATH = "/webhook"
BASE_WEBHOOK_URL = "https://botrealestateod.alwaysdata.net"

load_dotenv(find_dotenv())

bot = Bot(os.getenv('TG_TOKEN'), parse_mode=ParseMode.HTML)
dp = Dispatcher()


async def on_startup(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.set_webhook(f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}")


async def start_poling():
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


def start_webhook() -> None:
    dp.include_router(router)
    dp.startup.register(on_startup)
    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    # Register webhook handler on application
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)

    # Mount dispatcher startup and shutdown hooks to aiohttp application
    setup_application(app, dp, bot=bot)

    # And finally start webserver
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    start_webhook()