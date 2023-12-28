from binance_utils.web_socket import BinanceWebsocketMarkPrice, BinanceWebsocketUserData
from binance_utils.binance_api import client, send_telegram_message, open_position
from utils.mongodb import show_data_in_db, remove_object_from_coin
import asyncio
import time
import threading
import json


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
ticker_list = ws.ticker_list
user_data_ws = BinanceWebsocketUserData(client)
user_data_ws.ticker_stream_start()
last_order = user_data_ws.last_order
list_working_orders = asyncio.run(show_data_in_db())


def compare_order_prices_with_tickers(ticker_list: dict) -> None:
    while True:
        list_working_orders_copy = list_working_orders.copy()
        for order in list_working_orders_copy:
            if ticker_list.get(order['coin']):
                if (order['price'] * 0.9985) <= ticker_list[order['coin']] <= (order['price'] * 1.0015):
                    text_message = f"{order['coin']} -- {order['action']} NOW! ${order['price']}"
                    send_telegram_message(text_message)

                    asyncio.run(remove_object_from_coin(
                        coin=order['coin'],
                        price=order['price'],
                        action=order['action']
                    ))
                    thread_name = f"{order['coin']}-{order['price']}-{order['action']}-open_position-Thread"
                    threading.Thread(
                        target=open_position, 
                        name=thread_name,
                        kwargs={
                            'symbol' : order['coin'],
                            'side' : order['action'],
                            'price' : order['price'],
                            'user_data_ws' : user_data_ws.orders_user_data,
                            'ticker_list': ticker_list,
                            'is_breakout_strategy_enabled': trading_cnfg.is_breakout_strategy_enabled,
                            'take_price_percentage': trading_cnfg.take_price_percentage,
                            'stop_price_percentage': trading_cnfg.stop_price_percentage,
                            'position_size_in_dollars': trading_cnfg.position_size_in_dollars,
                            'trailing_stop_percent': trading_cnfg.trailing_stop_percent,
                            'order_market' : trading_cnfg.order_market

                        },
                    ).start()
                    list_working_orders.remove(order)
        time.sleep(1)


def start_trading_bot():
    threading.Thread(
        target=compare_order_prices_with_tickers, 
        name='compare_order_prices_with_tickers-Thread',
        args=(ticker_list,),
        daemon=True 
    ).start()





