from trading_bot import start_trading_bot
from loader import (
    start_webhook, 
    start_poling
)
import threading
import asyncio
import logging
import sys


if __name__ == '__main__':
    # logging.basicConfig(
    #     level=logging.DEBUG, 
    #     filename='log_file.log'
    # )
    start_trading_bot()
    start_webhook()
    # asyncio.run(start_poling())





