from trading_bot import start_trading_bot
from loader import (
    start_webhook, 
    start_poling
)

import asyncio
import logging
import sys


def main():
    start_trading_bot()
    start_webhook()
    # asyncio.run(start_poling())

if __name__ == '__main__':
    main()

    # logging.basicConfig(
    #     level=logging.DEBUG, 
    #     filename='log_file.log'
    # )
    # start_trading_bot()
    # start_webhook()
    # asyncio.run(start_poling())





