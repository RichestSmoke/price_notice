from binance_utils.web_socket import BinanceWebsocketMarkPrice, BinanceWebsocketUserData
from binance_utils.trading_levels import update_trading_levels
from utils.mongodb import show_data_in_db, remove_object_from_coin, update_data_on_db
from binance_utils.binance_api import client, logger, send_telegram_message, open_position
import asyncio
import schedule
import time
import threading
import json
from pprint import pprint
import traceback
from collections import deque
import logging


class TradingConfig():
    def __init__(
            self, 
            is_breakout_strategy_enabled=False,
            order_market=False,
            position_size_in_dollars=10,
            take_price_percentage=0.02,
            stop_price_percentage=0.008,
            trailing_stop_percent=0.0012
        ):
        data = self.load_data_from_file('config.json')
        self.is_breakout_strategy_enabled = data.get('breakout_strategy', is_breakout_strategy_enabled)
        self.order_market = data.get('order_market', order_market)
        self.position_size_in_dollars = data.get('position_size', position_size_in_dollars)
        self.take_price_percentage = data.get('take_price', take_price_percentage)
        self.stop_price_percentage = data.get('stop_price', stop_price_percentage)
        self.trailing_stop_percent = data.get('trailing_stop', trailing_stop_percent)


    def load_data_from_file(self, filename: str) -> dict:
        try:
            with open(filename, 'r') as json_file:
                return json.load(json_file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}


trading_cnfg = TradingConfig()
ws = BinanceWebsocketMarkPrice()
ws.ticker_stream_start()
ticker_and_price_dict = ws.ticker_and_price_dict
user_data_ws = BinanceWebsocketUserData(client)
user_data_ws.ticker_stream_start()
is_open_position_dict = user_data_ws.is_open_position_dict
last_order = user_data_ws.last_order
list_working_orders = asyncio.run(show_data_in_db())

unique_colors = deque([
    "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🟤", 
    "⚫", "⚪", "🟥", "🟧", "🟨", "🟩", "🟦", 
    "🟪", "🟫", "⬛", "⬜", "🔶", "🔷"
])

def start_update_trading_levels(list_working_orders: list):
    list_working_orders_copy = list_working_orders.copy()
    with open('trading_pair.json', 'r') as file:
        json_data = file.read()
    trading_pairs: list = json.loads(json_data)

    new_orders = []
    for symbol in trading_pairs:
        orders = update_trading_levels(
            client=client,
            list_working_orders=list_working_orders_copy,
            symbol=symbol
        )
        new_orders.extend(orders)
        time.sleep(30)

    if new_orders:
        db_result = asyncio.run(update_data_on_db(new_orders))
        list_working_orders.extend(new_orders)
        text = "Добавлены новые ордера:\n"
        for order in new_orders:
            text += f"{order['coin']}  -  {order['price']}$ {order['action']}\n"
        text += f"db: {db_result}"
        send_telegram_message(text)
    else:
        send_telegram_message("Новых ордеров нет!")


def run_scheduler(list_working_orders: list):
    try:
        # schedule.every(1).minute.do(start_update_trading_levels, list_working_orders)
        schedule.every().day.at("08:00").do(start_update_trading_levels, list_working_orders)
        schedule.every().day.at("20:00").do(start_update_trading_levels, list_working_orders)
        while True:
            schedule.run_pending()
            time.sleep(1) 
    except Exception as e:
        logger.error(f"run_scheduler Exception: {e}")
        logger.error(traceback.format_exc())
        send_telegram_message(f'Обновление уровней не работает\n{e}')



def compare_order_prices_with_tickers(ticker_and_price_dict: dict) -> None:
    while True:
        list_working_orders_copy = list_working_orders.copy()
        for order in list_working_orders_copy:
            if ticker_and_price_dict.get(order['coin']):
                if (order['price'] * 0.9985) <= ticker_and_price_dict[order['coin']] <= (order['price'] * 1.0015):
                    color_log = unique_colors.popleft()
                    if (order['coin'] not in is_open_position_dict) or (not is_open_position_dict[order['coin']]):
                        text_message = f"{order['coin']} - ${order['price']} {'📈' if order['action'] == 'SELL' else '📉'} NOW!"
                        send_telegram_message(text_message)
                        logger.info(f"{color_log} Entering the open_position: {order['coin']} - {order['price']}$ {order['action']}")
                        thread_name = f"{order['coin']}-{order['price']}-{order['action']}-open_position-Thread"
                        threading.Thread(
                            target=open_position, 
                            name=thread_name,
                            kwargs={
                                'symbol' : order['coin'],
                                'side' : order['action'],
                                'price' : order['price'],
                                'user_data_ws' : user_data_ws.orders_user_data,
                                'ticker_and_price_dict': ticker_and_price_dict,
                                'is_open_position_dict' : is_open_position_dict,
                                'is_breakout_strategy_enabled': trading_cnfg.is_breakout_strategy_enabled,
                                'color_log' : color_log,
                                'unique_colors' : unique_colors,
                                'take_price_percentage': trading_cnfg.take_price_percentage,
                                'stop_price_percentage': trading_cnfg.stop_price_percentage,
                                'position_size_in_dollars': trading_cnfg.position_size_in_dollars,
                                'trailing_stop_percent': trading_cnfg.trailing_stop_percent,
                                'order_market' : trading_cnfg.order_market
                            },
                        ).start()
                    elif is_open_position_dict[order['coin']]:
                        text_message = (
                            f"Unable to open a position: {order['coin']} - {order['price']}$ {order['action']}\n"
                            f"is_open_position_dict: {is_open_position_dict[order['coin']]}"
                        )
                        send_telegram_message(text_message)
                        logger.warning(f"{color_log} {text_message}")
                        unique_colors.append(color_log)

                    asyncio.run(remove_object_from_coin(
                        coin=order['coin'],
                        price=order['price'],
                        action=order['action']
                    ))
                    list_working_orders.remove(order)
        time.sleep(1)


def start_trading_bot():
    threading.Thread(
        target=compare_order_prices_with_tickers, 
        name='compare_order_prices_with_tickers-Thread',
        args=(ticker_and_price_dict,),
        daemon=True 
    ).start()

    threading.Thread(
        target=run_scheduler, 
        name='run_scheduler-Thread',
        args=(list_working_orders,), 
        daemon=True
    ).start()
    







