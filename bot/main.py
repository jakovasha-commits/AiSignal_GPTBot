import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers import routers


async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    for r in routers:
        dp.include_router(r)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
