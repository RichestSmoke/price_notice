from binance.um_futures import UMFutures
import websockets
import asyncio
import json
import certifi, os
import threading
import traceback
import time


class BinanceWebsocketMarkPrice:
    def __init__(self):
        os.environ['SSL_CERT_FILE'] = certifi.where()
        self.ticker_list = {}


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
                                self.ticker_list[data_item['s']] = float(data_item['p'])

                        except Exception as e:
                            print(f"Error processing message: {str(e)}")
                            if str(e) != 'string indices must be integers':
                                break
                            await asyncio.sleep(2)

            except:
                print("Connection closed")
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
        self.um_client = client


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
                            data = json.loads(msg)
                            if data['e'] == 'ORDER_TRADE_UPDATE':
                                order_info = {
                                    "pair" : data['o']['s'],
                                    "side" : data['o']['S'],
                                    "average_price" : float(data['o']['ap']),
                                    "order_status" : data['o']['X'], 
                                    "realized_profit_of_the_trade" : float(data['o']['rp'])
                                }
                                self.orders_user_data[data['o']['i']] = order_info
                                self.last_order.update(order_info)

                        except Exception as e:
                            print(f"Error processing message: {str(e)}")
                            if str(e) != 'string indices must be integers':
                                break
                            await asyncio.sleep(2)

            except:
                print("Connection closed")
                print('Ошибка:\n', traceback.format_exc())
                await asyncio.sleep(5)


    def __start_connection(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.__ws_connect())



    def ticker_stream_start(self):
        threading.Thread(target=self.__start_connection, name='user_data_stream_thread', daemon=True).start()
        threading.Thread(target=self.__renew_listen_key, name='renew_listen_key_thread', daemon=True).start()




        