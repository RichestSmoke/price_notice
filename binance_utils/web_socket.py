from binance.um_futures import UMFutures
import websockets
import queue  
import asyncio
import json
import certifi, os
import threading
import traceback
import time
import logging


class BinanceWebsocketMarkPrice:
    def __init__(self):
        os.environ['SSL_CERT_FILE'] = certifi.where()
        self.ticker_and_price_dict = {}


    async def __ws_connect(self):
        while True:
            try:
                async with websockets.connect("wss://fstream.binance.com/ws") as ws:
                    params = {
                        "method": "SUBSCRIBE",
                        "params": ["!markPrice@arr@1s"],
                        "id": 1
                    }
                    await ws.send(json.dumps(params))

                    while True:
                        try:
                            msg = await ws.recv()
                            data = json.loads(msg)
                            for data_item in data:
                                self.ticker_and_price_dict[data_item['s']] = float(data_item['p'])

                        except Exception as e:
                            logging.error(f"BinanceWebsocketMarkPrice. Message: {str(e)}")
                            if str(e) != 'string indices must be integers':
                                break
                            await asyncio.sleep(2)

            except Exception as e:
                logging.error(f"BinanceWebsocketMarkPrice: Connection closed! Message: {str(e)}")
                await asyncio.sleep(10)


    def __start_connection(self):
        asyncio.run(self.__ws_connect())


    def ticker_stream_start(self):
        threading.Thread(
            target=self.__start_connection, 
            name='ticker_stream_thread', 
            daemon=True
        ).start()





class BinanceWebsocketUserData:
    def __init__(self, client: UMFutures):
        os.environ['SSL_CERT_FILE'] = certifi.where()
        self.orders_user_data = {}
        self.last_order = {}
        self.account_balance_in_dollar = 0
        self.is_open_position_dict = {}
        self.um_client = client
        self.order_queue = queue.Queue()  # Создаем синхронную очередь

    def __renew_listen_key(self):
        while True:
            time.sleep(30)
            self.um_client.renew_listen_key(self.listen_key)
            time.sleep(3000)

    async def __ws_connect(self):
        while True:
            try:
                self.listen_key = self.um_client.new_listen_key()['listenKey']
                async with websockets.connect(f"wss://fstream.binance.com/ws/{self.listen_key}") as ws:
                    while True:
                        try:
                            msg = await ws.recv()
                            self.order_queue.put(msg) 
                        except Exception as e:
                            if str(e) != 'string indices must be integers':
                                break
                            logging.error(f"BinanceWebsocketUserData. Message: {str(e)}")
                            time.sleep(2)

            except Exception as e:
                logging.error(f"BinanceWebsocketUserData: Connection closed! Message: {str(e)}")
                logging.error(traceback.format_exc())
                time.sleep(5)

    def process_orders(self):
        while True:
            try:
                msg = self.order_queue.get()  # Получаем сообщение из очереди
                data = json.loads(msg)
                if data['e'] == 'ORDER_TRADE_UPDATE':
                    order_info = {
                        "pair": data['o']['s'],
                        "side": data['o']['S'],
                        "average_price": float(data['o']['ap']),
                        "order_status": data['o']['X'],
                        "realized_profit_of_the_trade": float(data['o']['rp'])
                    }
                    self.orders_user_data[data['o']['i']] = order_info
                    self.last_order.update(order_info)

                if data['e'] == 'ACCOUNT_UPDATE':
                    if data['a']['m'] == 'ORDER':
                        for asset in data['a']['B']:
                            if asset['a'] == 'USDT':
                                self.account_balance_in_dollar = float(asset['wb'])
                        for symbol in data['a']['P']:
                            self.is_open_position_dict[symbol['s']] = float(symbol['pa'])

            except Exception as e:
                logging.error(f"BinanceWebsocketUserData: Error processing order: {e}")
                logging.error(traceback.format_exc())

    def __start_connection(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.__ws_connect())

    def ticker_stream_start(self):
        threading.Thread(target=self.__start_connection, name='user_data_stream_thread', daemon=True).start()
        threading.Thread(target=self.process_orders, name='process_orders_thread', daemon=True).start()
        threading.Thread(target=self.__renew_listen_key, name='renew_listen_key', daemon=True).start()







# if __name__ == "__main__":
#     from binance_api import client
#     from pprint import pprint
#     import time
#     ws = BinanceWebsocketUserData(client)
#     ws.ticker_stream_start()

#     while True:
#         print(f'account_balance_in_dollar: {ws.account_balance_in_dollar}')
#         print(f'is_open_position_dict: {ws.is_open_position_dict}')

#         time.sleep(10)
        









# class BinanceWebsocketUserData:
#     def __init__(self, client: UMFutures):
#         os.environ['SSL_CERT_FILE'] = certifi.where()
#         self.orders_user_data = {}
#         self.last_order = {}
#         self.um_client = client


#     def __renew_listen_key(self):
#         while True:
#             time.sleep(30)
#             self.um_client.renew_listen_key(self.listen_key)
#             time.sleep(3000)

#     async def __ws_connect(self):
#         while True:
#             try:
#                 self.listen_key = self.um_client.new_listen_key()['listenKey']
#                 async with websockets.connect(f"wss://fstream.binance.com/ws/{self.listen_key}") as ws:
#                     while True:
#                         try:
#                             msg = await ws.recv()
#                             data = json.loads(msg)
#                             if data['e'] == 'ORDER_TRADE_UPDATE':
#                                 order_info = {
#                                     "pair" : data['o']['s'],
#                                     "side" : data['o']['S'],
#                                     "average_price" : float(data['o']['ap']),
#                                     "order_status" : data['o']['X'], 
#                                     "realized_profit_of_the_trade" : float(data['o']['rp'])
#                                 }
#                                 self.orders_user_data[data['o']['i']] = order_info
#                                 self.last_order.update(order_info)

#                         except Exception as e:
#                             logging.error(f"BinanceWebsocketUserData. Message: {str(e)}")
#                             if str(e) != 'string indices must be integers':
#                                 break
#                             await asyncio.sleep(2)

#             except:
#                 logging.error(f"BinanceWebsocketUserData: Connection closed! Message: {str(e)}")
#                 print('Ошибка:\n', traceback.format_exc())
#                 await asyncio.sleep(5)


#     def __start_connection(self):
#         loop = asyncio.new_event_loop()
#         asyncio.set_event_loop(loop)
#         loop.run_until_complete(self.__ws_connect())
        

#     def ticker_stream_start(self):
#         threading.Thread(target=self.__start_connection, name='user_data_stream_thread', daemon=True).start()
#         threading.Thread(target=self.__renew_listen_key, name='renew_listen_key_thread', daemon=True).start()
