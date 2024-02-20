from binance.um_futures import UMFutures
from binance.error import ClientError
from dotenv import load_dotenv, find_dotenv
from collections import deque
from typing import Optional
import requests
import traceback
import os
import logging
import math
import time


load_dotenv(find_dotenv())
logger = logging.getLogger(__name__)
logging.basicConfig(
        filename="log_file.log",
        style='{',
        format='{levelname} ({asctime}): {message} (Line: {lineno}) [{filename}]',
        level=logging.INFO, 
    )


def send_telegram_message(message: str, chat_id=425136998) -> None:
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{os.getenv('TG_TOKEN')}/sendMessage", 
            params=dict(chat_id=chat_id, text=message)
        )
        response.raise_for_status() 

    except requests.exceptions.RequestException as e:
        logger.error(f"💔 Error send_telegram_message: {e}")


client = UMFutures(
    os.getenv('API_KEY_BINANCE'), 
    os.getenv('API_SECRET_BINANCE')
)


def get_filters_exchange_info() -> dict:
    result = {}
    response = client.exchange_info()
    for symbol in response['symbols']:
        result[symbol['symbol']] = {
            'tickSize' : float(symbol['filters'][0]['tickSize']),
            'stepSize' : float(symbol['filters'][1]['stepSize']),
            'min_notional' : float(symbol['filters'][5]['notional'])
        }
    return result


TRADE_FILTERS = get_filters_exchange_info()


def new_order_limit(symbol: str, side: str, quantity: float, price: float, color_log="") -> Optional[int]:
    try:
        response = client.new_order(
            symbol=symbol,
            side=side,
            type='LIMIT',
            quantity=quantity,
            price=price,
            timeInForce='GTC'
        )
        logging.info(
            f"{color_log} new_order_limit: GOOD! orderId: {response['orderId']}, "
            f"params: symbol={symbol}, side={side}, quantity={quantity}, price={price}"
        )
        return response['orderId']

    except ClientError as e:
        message = (
            f"💔 Exept new_order_limit\n"
            f"{symbol} - {side} - ${price}, quantity: {quantity}\n"
            f"Found error. status: {e.status_code}, error code: {e.error_code}, error message: {e.error_message}"
        )
        logging.error(color_log + ' ' + message)
        send_telegram_message(message)
        return None


def new_order_market(symbol: str, side: str, quantity: float, color_log="") -> Optional[int]:
    try:
        response = client.new_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=quantity,
        )
        logging.info(
            f"{color_log} new_order_market: GOOD! orderId: {response['orderId']}, "
            f"params: symbol={symbol}, side={side}, quantity={quantity}"
        )
        return response['orderId']

    except ClientError as e:
        message = (
            f"💔 Exept new_order_market\n"
            f"{symbol} - {side}, quantity: {quantity}\n"
            f"Found error. status: {e.status_code}, error code: {e.error_code}, error message: {e.error_message}"
        )
        logging.error(color_log + ' ' + message)
        send_telegram_message(message)
        return None


def new_stop_order(symbol: str, side: str, stop_price: float, color_log="") -> Optional[int]:
    try:
        response = client.new_order(
            symbol=symbol,
            side='SELL' if side == 'BUY' else 'BUY',
            type='STOP_MARKET',
            stopPrice=stop_price,
            closePosition='true',
            timeInForce = 'GTE_GTC'
        )
        logging.info(
            f"{color_log} new_stop_order: GOOD! orderId: {response['orderId']}, "
            f"params: symbol={symbol}, side={side}, stop_price={stop_price}"
        )
        return response['orderId']

    except ClientError as e:
        message = (
            f"💔 Exept new_stop_order\n"
            f"{symbol} - {side} - stop_price: ${stop_price}\n"
            f"Found error. status: {e.status_code}, error code: {e.error_code}, error message: {e.error_message}"
        )
        logging.error(color_log + ' ' + message)
        send_telegram_message(message)
        return None


def new_take_profit_order(
    symbol: str, side: str, quantity: float, 
    take_price: float, take_price_trigger: float, color_log=""
) ->  Optional[int]:
    try:
        response = client.new_order(
            symbol=symbol,
            side='SELL' if side == 'BUY' else 'BUY',
            type='TAKE_PROFIT',
            quantity=quantity,
            price=take_price,
            stopPrice=take_price_trigger,
            reduceOnly=True,
            timeInForce='GTE_GTC'
        )
        logging.info(
            f"{color_log} new_take_profit_order: GOOD! orderId: {response['orderId']}, "
            f"params: symbol={symbol}, side={side}, quantity={quantity}, "
            f"take_price={take_price}, take_price_trigger={take_price_trigger}"
        )
        return response['orderId']

    except ClientError as e:
        message = (
            f"💔 Except new_take_profit_order\n"
            f"{symbol} - {side} - quantity: {quantity}\ntake_price: ${take_price}, take_price_trigger: ${take_price_trigger}\n"
            f"Found error. status: {e.status_code}, error code: {e.error_code}, error message: {e.error_message}"
        )
        logging.error(color_log + ' ' + message)
        send_telegram_message(message)
        return None


def round_step_size(number: float, precision: float) -> float:
    i = 0
    while True:
        if math.isclose(precision, 1):
            break
        else:
            precision *= 10
            i += 1
    number = round(number, i)
    return number


def monitor_postion(
    symbol: str,
    price: float,
    side: str,
    average_price: float,
    user_data_ws: dict,
    ticker_and_price_dict: dict,
    position_order_id: int,
    stop_order_id: int,
    take_profit_order_id:int,
    trailing_stop_percent: float,
    color_log: str,
    unique_colors: deque
) -> None:
    trailing_stop_trigger_price = average_price * (1 + trailing_stop_percent) if side == 'BUY' else average_price * (1 - trailing_stop_percent)
    stop_loss_adjusted = False
    print(user_data_ws)
    while True:
        # Проверка на срабатывания стопа
        if user_data_ws[stop_order_id]['order_status'] == 'FILLED':
            logger_text = f"{color_log} STOP LOSS! {symbol} - {price}$ {side}"
            break

        # Проверка на срабатывания тейк профита 
        elif user_data_ws[take_profit_order_id]['order_status'] == 'FILLED':
            logger_text = f"{color_log} TAKE PROFIT! {symbol} - {price}$ {side}"
            break

        elif (user_data_ws[take_profit_order_id]['order_status'] == 'EXPIRED') or (user_data_ws[stop_order_id]['order_status'] == 'EXPIRED'):
            logger_text = f"{color_log} (TAKE PROFIT or STOP LOSS) = EXPIRED! {symbol} - {price}$ {side}"
            break

        # Сдвиг стопа в б/у 
        elif not stop_loss_adjusted:
            if ticker_and_price_dict[symbol] >= trailing_stop_trigger_price if side == 'BUY' else ticker_and_price_dict[symbol] <= trailing_stop_trigger_price:
                logger.warning(f"{color_log} TRAILING STOP LOSS! position_order_id: {position_order_id} / {symbol} - {price}$ {side}")
                stop_loss_adjusted = True
                try:
                    client.cancel_order(symbol=symbol, orderId=stop_order_id)
                    stop_price = round_step_size(
                        average_price * (1.002 if side == 'BUY' else 0.998), 
                        TRADE_FILTERS[symbol]['tickSize']
                    )
                    user_data_ws.pop(stop_order_id, None)
                    stop_order_id = new_stop_order(symbol, side, stop_price, color_log)
                    logger.info(f"{color_log} NEW STOP LOSS: {symbol} - {price}$ {side}; stop_price: {stop_price}, stop_order_id: {stop_order_id}")

                except ClientError as e:
                    logger.error(
                        f"{color_log} Cancel_order, position_order_id: {position_order_id} / {symbol} - {price}$ {side},\n"
                        f"status: {e.status_code}, error code: {e.error_code}, error message: {e.error_message}"
                    )
                    send_telegram_message(f'💔 Eror TRAILING STOP LOSS! {symbol} - {price}$ {side}, Проверь стоп лосс в позиции')

        time.sleep(2)
    logger.info(logger_text)
    send_telegram_message(logger_text)
    unique_colors.append(color_log)
    user_data_ws.pop(position_order_id, None)
    user_data_ws.pop(stop_order_id, None)
    user_data_ws.pop(take_profit_order_id, None)
    

def open_position(
    symbol: str, side: str, price: float, user_data_ws: dict,
    ticker_and_price_dict: dict,
    is_open_position_dict: dict,
    is_breakout_strategy_enabled: bool,
    color_log: str,
    unique_colors: deque,
    take_price_percentage: float = 0.01,
    stop_price_percentage: float = 0.005,
    position_size_in_dollars: int = 10,
    trailing_stop_percent: float = 0.01,
    order_market = False
) -> None:
    def execute_close_trade():
        time.sleep(1.5)
        if is_open_position_dict.get(symbol):
            send_telegram_message(f"Открытая позиция: {symbol} - {price}$ {side}, пробую закрыть...")
            logger.info(
                f"{color_log} Eror open_position-Thread[Block except]: {symbol} - {price}$ {side}, "
                f"is_open_position_dict = {is_open_position_dict[symbol]}\n"
                f"Open position, trying close position..."
            )
            close_position_order_id = new_order_market(
                symbol=symbol,
                side= 'BUY' if side == 'SELL' else 'SELL',
                quantity=abs(is_open_position_dict[symbol]),
                color_log=color_log
            )
            time.sleep(2)
            if close_position_order_id:
                send_telegram_message(f"Позиция закрыта! {symbol} - {price}$ {side}")
                logger.info(f"{color_log} Позиция закрыта! {symbol} - {price}$ {side}")
                user_data_ws.pop(close_position_order_id, None)
                user_data_ws.pop()
            else:
                send_telegram_message(f"Ошибка при закрытии позиции, нужно закрыть вручную! {symbol} - {price}$ {side}")
                logger.warning(f"{color_log} Error when closing a position, you need to close it manually! {symbol} - {price}$ {side}")

    
    try:
        if is_breakout_strategy_enabled:
            side = 'BUY' if side == 'SELL' else 'SELL'
        
        price = round_step_size(price, TRADE_FILTERS[symbol]['tickSize'])
        if position_size_in_dollars < TRADE_FILTERS[symbol]['min_notional']:
            logger.info(
                f"{color_log} POSITION_SIZE_IN_DOLLARS < MIN_NOTIONAL - STOP OPEN_POSITION: {symbol} - {price}$ {side}\n"
                f"POSITION_SIZE_IN_DOLLARS: {position_size_in_dollars}, MIN_NOTIONAL: {TRADE_FILTERS[symbol]['min_notional']}"
            )
            send_telegram_message(f"POSITION_SIZE_IN_DOLLARS < MIN_NOTIONAL - STOP OPEN_POSITION: {symbol} - {price}$ {side}")
            unique_colors.append(color_log)
            return None

        quantity = round_step_size(
            position_size_in_dollars / price,
            TRADE_FILTERS[symbol]['stepSize']
        )
        if order_market:
            position_order_id = new_order_market(symbol, side, quantity, color_log)
        else:
            position_order_id = new_order_limit(symbol, side, quantity, price, color_log)
        time.sleep(1)
        if position_order_id:
            while True:
                if position_order_id in user_data_ws:
                    if user_data_ws[position_order_id]['order_status'] == 'FILLED':
                        average_price = user_data_ws[position_order_id]['average_price']
                        break

                    elif user_data_ws[position_order_id]['order_status'] == 'CANCELED' or 'EXPIRED':
                        logger.info(f"{color_log} POSITION_ORDER_ID == 'CANCELED' or 'EXPIRED' - STOP OPEN_POSITION: {symbol} - {price}$ {side}, quantity: {quantity}")
                        send_telegram_message(f"POSITION_ORDER_ID == 'CANCELED' or 'EXPIRED' - STOP OPEN_POSITION: {symbol} - {price}$ {side}")
                        user_data_ws.pop(position_order_id, None)
                        execute_close_trade()
                        unique_colors.append(color_log)
                        return None
                time.sleep(0.5)

        else:
            logger.info(f"{color_log} POSITION_ORDER_ID == NONE - STOP OPEN_POSITION: {symbol} - {price}$ {side}, quantity: {quantity}")
            send_telegram_message(f"POSITION_ORDER_ID == NONE - STOP OPEN_POSITION: {symbol} - {price}$ {side}")
            unique_colors.append(color_log)
            return None

        stop_price = round_step_size(
            (average_price * ((1 - stop_price_percentage) if side == 'BUY' else (1 + stop_price_percentage))), 
            TRADE_FILTERS[symbol]['tickSize']
        )
        stop_order_id = new_stop_order(symbol, side, stop_price, color_log)
        multiplier = 1 if side == 'BUY' else -1
        take_price = round_step_size(average_price * (1 + multiplier * take_price_percentage), TRADE_FILTERS[symbol]['tickSize'])
        take_price_trigger = round_step_size(
            (take_price - multiplier * (10 * TRADE_FILTERS[symbol]['tickSize'])),
            TRADE_FILTERS[symbol]['tickSize']
        )
        take_profit_order_id = new_take_profit_order(symbol, side, quantity, take_price, take_price_trigger, color_log)
        logger.info(
            f"{color_log} Entering the monitor_position: {symbol} - {price}$ {side}\n"
            f"quantity: {quantity}, average_price: {average_price}, stop_price: {stop_price}, take_price: {take_price}, take_price_trigger: {take_price_trigger}\n"
            f"position_order_id: {position_order_id}, stop_order_id: {stop_order_id}, take_profit_order_id: {take_profit_order_id}"
        )
        time.sleep(1.5)
        monitor_postion(
            symbol=symbol,
            price=price,
            side=side,
            average_price=average_price,
            user_data_ws=user_data_ws,
            ticker_and_price_dict=ticker_and_price_dict,
            position_order_id=position_order_id,
            stop_order_id=stop_order_id,
            take_profit_order_id=take_profit_order_id,
            trailing_stop_percent=trailing_stop_percent,
            color_log=color_log,
            unique_colors=unique_colors
        )
    except Exception as e:
        time.sleep(1)
        logger.error(f"{color_log}💔 Eror open_position-Thread: {symbol} - {price}$ {side}\n{e}")
        logger.error(color_log + traceback.format_exc())
        send_telegram_message(f"💔 Eror open_position-Thread\n{symbol} - {price}$ {side}\n{e}\n")
        user_data_ws.pop(position_order_id, None)
        user_data_ws.pop(stop_order_id, None)
        user_data_ws.pop(take_profit_order_id, None)
        execute_close_trade()
        unique_colors.append(color_log)
        





    

# if __name__ == '__main__':
#     from web_socket import BinanceWebsocketMarkPrice, BinanceWebsocketUserData
    
#     ws = BinanceWebsocketMarkPrice()
#     ws.ticker_stream_start()
#     ticker_list = ws.ticker_list

#     user_data_ws = BinanceWebsocketUserData(client)
#     user_data_ws.ticker_stream_start()
#     last_order = user_data_ws.last_order
#     time.sleep(10)
#     open_position(
#         symbol="MATICUSDT", side="BUY", price=0.7906, user_data_ws=user_data_ws.orders_user_data,
#         ticker_list=ticker_list,
#         take_price_percentage = 0.005,
#         stop_price_percentage = 0.005,
#         position_size_in_dollars = 10,
#         trailing_stop_percent = 0.003,
#         order_market = True
#     )






# COIN = 'MATICUSDT'


# open_position(COIN, "SELL", 0.82)

# new_order_market('MATICUSDT', 'SELL', 9)
# stop_order('MATICUSDT', 'SELL', 0.81)

# from binance.client import Client
# from binance.exceptions import BinanceAPIException 
# from binance.helpers import round_step_size 
# from unicorn_binance_websocket_api.manager import BinanceWebSocketApiManager
# from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient

# def message_hendler(_, message):
#     print(message)


# wss_cl = UMFuturesWebsocketClient(on_message=message_hendler)
# wss_cl.user_data

# import keys
# import pandas as pd
# import numpy as np
# import certifi
# import os
# import json
# import certifi
# import threading
# import math
# import time
# import talib 

# client = UMFutures(keys.API_KEY, keys.API_SECRET)


# my_client = Client(keys.API_KEY, keys.API_SECRET)


# os.environ['SSL_CERT_FILE'] = certifi.where()

# # logging.getLogger("unicorn_binance_websocket_api")
# # logging.basicConfig(level=logging.DEBUG,
# #                     filename=os.path.basename(__file__) + '.log',
# #                     format="{asctime} [{levelname:8}] {process} {thread} {module}: {message}",
# #                     style="{")


# #----------------------------- WEBSOCKET -----------------------------------

# def process_new_receives_mark_price(stream_data, stream_buffer_name=False):
#     mark_price_data = json.loads(stream_data)
#     try:
#         mark_price_data = mark_price_data['data']
#         global mark_price
#         mark_price = float(mark_price_data['p'])
#     except:
#         pass
   

# def process_new_receives_stream_data(stream_data, stream_buffer_name=False):
#     stream_data = json.loads(stream_data)
#     global order_trade_update
#     try:
#         if stream_data['e'] == 'ORDER_TRADE_UPDATE':
#             order_trade_update = {
#                 "pair" : stream_data['o']['s'],
#                 "side" : stream_data['o']['S'],
#                 "average_price" : float(stream_data['o']['ap']),
#                 "order_id" : stream_data['o']['i'], 
#                 "order_status" : stream_data['o']['X'], 
#                 "realized_profit_of_the_trade" : float(stream_data['o']['rp'])
#             }
        
#     except:
#         pass
    

# ubwa = BinanceWebSocketApiManager(exchange="binance.com-futures")
# userdata_stream_id = ubwa.create_stream(["arr"],
#                                         ["!userData"],
#                                         api_key=keys.api_key,
#                                         api_secret=keys.api_secret,
#                                         process_stream_data=process_new_receives_stream_data)
# ubwa.create_stream(["markPrice@1s"], ["imxusdt"], process_stream_data=process_new_receives_mark_price)

# def create_dict_orders():
#     global dict_orders 
#     dict_orders = {}
#     while True:
#         try:
#             dict_orders[order_trade_update["order_id"]] = {
#                 "average_price" : order_trade_update["average_price"],
#                 "order_status" : order_trade_update["order_status"], 
#                 "realized_profit_of_the_trade" : order_trade_update["realized_profit_of_the_trade"]
#             }
#         except:
#             pass
#         time.sleep(0.00005)

# threading.Thread(target=create_dict_orders).start()

# #----------------------------- WEBSOCKET END -----------------------------------

# def get_historical_klines (ticker):
#     df0 = pd.DataFrame(my_client.futures_historical_klines(ticker, '5m', '100 hours ago UTC', 'now UTC'))
#     df = df0.drop([6, 7, 8, 9, 10, 11], axis=1)
#     df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
#     df = df.set_index('Time')
#     df.index = pd.to_datetime(df.index, unit='ms')
#     df = df.astype(float)
#     return df

# # df = get_historical_klines('BNBUSDT')

# # rsi = talib.RSI(df['Close'], 14)
# # print(rsi)
# # print(get_historical_klines('ETHUSDT'))


# # macd = talib.MACD()


# # def top_coins():
# #     all_tickers = pd.DataFrame(my_client.get_ticker())
# #     usdt_tickers = all_tickers[all_tickers.symbol.str.contains('USDT')]
# #     work = usdt_tickers[~((usdt_tickers.symbol.str.contains('UP')) | (usdt_tickers.symbol.str.contains('DOWN')))]
# #     top_coin = work[work.priceChangePercent == work.priceChangePercent.max()]
# #     top_coin = top_coin.symbol.values[0]
# #     #bond = all_tickers[all_tickers.symbol.str.contains('BONDUSDT')]
# #     #print(bond)
# #     return top_coin 
# # balance = my_client.futures_account_balance()[6]['balance']

# #print(balance)

# #print(top_coins())


# # def round_step_size(number, precision):
# #     i = 0
# #     while True:
# #         if math.isclose(precision, 1):
# #             break
# #         else:
# #             precision *= 10
# #             i += 1
# #     number = round(number, i)
# #     return number


# def new_order(symbol, side, quantity, price):
#     try:
#         order = my_client.futures_create_order(
#         symbol=symbol,
#         side=side,
#         type='LIMIT',
#         quantity=quantity,
#         price=str(price),
#         timeInForce='GTC')

#         order_id = order['orderId']
#         # entryPrice = order['entryPrice']
#         print(f'Order good // orderId: {order_id}')
#         time.sleep(1) 
#         return order_id

#     except BinanceAPIException as e:
#         print("---Cant buy---")
#         print(e.message, '///', e.code)
#         return None
    
    
# def stop_order(symbol, side, stop_price):
#     try:
#         stop_order = my_client.futures_create_order(
#         symbol=symbol,
#         side="SELL" if side == "BUY" else "BUY",
#         type='STOP_MARKET',
#         stopPrice=str(stop_price),
#         closePosition='true',
#         timeInForce = 'GTE_GTC')    

#         order_id = stop_order['orderId']
#         print(f'Stop good // stop_order_id: {order_id}')
#         return order_id

#     except BinanceAPIException as e: 
#         print("---Cant stop---")
#         print(e.message, '///', e.code)
#         return None


# def take_profit_order(symbol, side, quantity, take_price, take_price_tick):

#     try:
#         take_order = my_client.futures_create_order(
#         symbol=symbol,
#         side="SELL" if side == "BUY" else "BUY",
#         type='TAKE_PROFIT',
#         quantity=quantity,
#         price=str(take_price),
#         stopPrice=str(take_price_tick),
#         reduceOnly=True,
#         timeInForce='GTE_GTC')

#         take_order_id = take_order['orderId']
#         print(f'Take good // take_order_id: {take_order_id}')
#         return take_order_id

#     except BinanceAPIException as e:
#         print("---Can't Take---")
#         print(e.message, '///', e.code)
    

# def take_profit_order_market(symbol, take_price):
#     try:
#         take_order = my_client.futures_create_order(
#         symbol=symbol,
#         side="SELL" if side == "BUY" else "BUY",
#         type='TAKE_PROFIT_MARKET',
#         stopPrice=str(take_price),
#         timeInForce='GTE_GTC',
#         closePosition='true')
        
#         take_order_id = take_order['orderId']
#         print(f'Take market good // take_market_id: {take_order_id}')
#         return take_order_id

#     except BinanceAPIException as e:
#         print("---Cant Take---")
#         print(e.message, '///', e.code)


# def cancel_order(symbol, orderId):
#     my_client.futures_cancel_order(symbol=symbol, orderId=orderId)
    



# def create_take_proft_grid(price, side, first_order_tp, step_grid_tp, quantity_orders_tp):
#     quantity_one_orders = round_step_size(quantity / quantity_orders_tp, step_size_Qty)
#     list_id_tp = []
#     for i in range(quantity_orders_tp):
        # if side == 'BUY':
        #     take_price = round_step_size(price * (1 + first_order_tp + (i * step_grid_tp)), tick_size)
        #     take_price_trigger = round_step_size((take_price - (3 * tick_size)), tick_size) 
        
        # elif side == 'SELL':
        #     take_price = round_step_size(price * (1 - first_order_tp - (i * step_grid_tp)), tick_size)
        #     take_price_trigger = round_step_size((take_price + (3 * tick_size)), tick_size)
        
#         if i < quantity_orders_tp - 1:
#             take_order_id = take_profit_order(symbol=symbol, 
#                                                 side=side, 
#                                                 quantity=quantity_one_orders, 
#                                                 take_price=take_price,
#                                                 take_price_tick=take_price_trigger)
        
#         if i == quantity_orders_tp - 1:
#             take_order_id = take_profit_order_market(symbol, take_price)
#             last_take_price = take_price
#         list_id_tp.append(take_order_id)
#         i += 1
#         time.sleep(1)
#     return list_id_tp, last_take_price

      

# def open_and_monitor_position2(open_position=False):
#     order_id = new_order(symbol, side, quantity, price)
#     print('Waiting to enter a position...')
# # нужно дописать проверку, если по какой-то причине ордер не примет 
#     while True:
#         if order_id in dict_orders:
#             if dict_orders[order_id]["order_status"] == 'FILLED':
#                 print('Got into position')
#                 break
# # нужно дописать проверку, если цена уйдет не исполнив мою лимитную заявку, что бы код не зациклился на этом шаге 
#         time.sleep(1) 

    
#     average_price = dict_orders[order_id]["average_price"]
#     open_position = True
#     stop_price = stop_price = round_step_size((average_price * ((1 - stop_price_percentage) if side == 'BUY' else (1 + stop_price_percentage))), tick_size)
#     print(f"price: {price}, average_price:{average_price}, stop_price: {stop_price}")
#     stop_order_id = stop_order(symbol, side, stop_price)
#     tp_orders_id, last_take_price = create_take_proft_grid(price=average_price, 
#                                                            side=side, 
#                                                            first_order_tp=0.01, 
#                                                            step_grid_tp=0.005, 
#                                                            quantity_orders_tp=4)
#     # Monitor position
#     # Процент на который будет сдвигаться стоплос, если цена идет в мою сторону
#     SL_adjustment_percent = 0.001 
#     # Процент который является триггером для сдвига стоплоса  
#     signal_to_SL_adjustment_percent = 0.001
#     print('Entering the Monitor position loop...')

#     while True:
#         # Проверка на срабатывания стопа
#         if dict_orders[stop_order_id]["order_status"] == 'FILLED':
#             print('Stop loss successful')
#             break

#         # Сдвиг стопа в б/у и выше 
#         elif mark_price >= average_price * (1 + signal_to_SL_adjustment_percent) if side == 'BUY' else mark_price <= average_price * (1 - signal_to_SL_adjustment_percent):
#             print('пробует передвинуть ордер')
#             print(symbol, stop_order_id)
#             try:
#                 my_client.futures_cancel_order(symbol=symbol, orderId=stop_order_id)
#                 print(f'Cancellation of stop loss, the price is more than the entry price by {signal_to_SL_adjustment_percent * 100}%')
#                 print(f'Old stop_pice {stop_price}')
#                 stop_price = round_step_size(stop_price * (1 + SL_adjustment_percent if side == 'BUY' else 1 - SL_adjustment_percent), tick_size)
#                 print(f'New stop_pice {stop_price}')
#                 dict_orders.pop(stop_order_id, None)
#                 stop_order_id = stop_order(symbol, side, stop_price)
#                 signal_to_SL_adjustment_percent += SL_adjustment_percent
            
#             except BinanceAPIException as e:
#                 print('except futures_cancel_order')
#                 print(e.message, '///', e.code)

#         # Проверка на исполнение воследнего тейк профита 
#         if tp_orders_id[-1] in dict_orders:
#             if dict_orders[tp_orders_id[-1]]["order_status"] == 'FILLED':
#                 print('Last take successful')
#                 break
#         time.sleep(1) 

#     dict_orders.pop(order_id, None)
#     dict_orders.pop(stop_order_id, None)
#     for id in tp_orders_id:
#         dict_orders.pop(id, None)
#     print(dict_orders)
#     print('Finish')
#     open_position = False
#     return open_position
              


# symbol='IMXUSDT'
# quantity = 40
# # price=2.248
# side = 'SELL'
# stop_price_percentage = 0.005

# filters = my_client.get_symbol_info(symbol=symbol)
# filters = filters['filters']
# tick_size = float(filters[0]['tickSize'])
# step_size_Qty = float(filters[1]['stepSize'])

# price = round_step_size((float(mark_price) - 2 * tick_size), tick_size)
# print(price)
# open_and_monitor_position2()