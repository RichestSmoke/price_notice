from binance_utils.web_socket import BinanceWebsocketMarkPrice, BinanceWebsocketUserData
from binance_utils.binance_api import client, send_telegram_message, open_position
from utils.mongodb import show_data_in_db, remove_object_from_coin
import asyncio
import time
import threading


POSITION_SIZE_IN_DOLLARS = 10
TAKE_PRICE_PERCENTAGE = 0.015
STOP_PRICE_PERCENTAGE = 0.0075


ws = BinanceWebsocketMarkPrice()
ws.ticker_stream_start()
ticker_list = ws.ticker_list

user_data_ws = BinanceWebsocketUserData(client)
user_data_ws.ticker_stream_start()
last_order = user_data_ws.last_order
list_working_orders = asyncio.run(show_data_in_db())


def open_and_monitoring_position():
    while True:
        ...



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
                        args=(
                            order['coin'],
                            order['action'],
                            order['price'],
                            user_data_ws.orders_user_data,
                            TAKE_PRICE_PERCENTAGE,
                            STOP_PRICE_PERCENTAGE,
                            POSITION_SIZE_IN_DOLLARS,
                            False,
                        )).start()
                    list_working_orders.remove(order)
        time.sleep(1)


def start_trading_bot():
    threading.Thread(
        target=compare_order_prices_with_tickers, 
        name='compare_order_prices_with_tickers-Thread',
        args=(ticker_list,),
        daemon=True 
    ).start()





