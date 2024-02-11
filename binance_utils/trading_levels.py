from binance.um_futures import UMFutures
from datetime import datetime, timedelta
from dotenv import load_dotenv, find_dotenv
from scipy.signal import find_peaks
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
import requests
import json
import time
import os
import matplotlib




load_dotenv(find_dotenv())


def send_telegram_photo(symbol: str):
    url = f"https://api.telegram.org/bot{os.getenv('TG_TOKEN')}/sendPhoto"
    params = {
        'chat_id': '@Three_Candle', 
        'caption': symbol
    }
    with open('candlestick_chart.jpg', 'rb') as photo_file:
        files = {'photo': photo_file}
        response = requests.post(url, files=files, data=params)



def get_historical_klines(
    client: UMFutures, symbol: str, interval = '15m', 
    startTime=None, endTime=None, limit=1500
) -> pd.DataFrame:
    df = pd.DataFrame(
        client.klines(
            symbol=symbol,
            interval=interval,
            startTime=startTime,
            endTime=endTime,
            limit=limit
        )
    )
    df = df.drop([6, 7, 8, 9, 10, 11], axis=1)
    df.columns = ['Time', 'Open', 'High', 'Low', 'Close', 'Volume']
    df = df.astype(float)
    df['Time'] = pd.to_datetime(df['Time'], unit='ms')
    return df


def get_df_klines_1_month(client: UMFutures, symbol: str):
    end_time = datetime.utcnow() - timedelta(hours=372)
    start_time = end_time - timedelta(hours=375)
    df1 = get_historical_klines(client, symbol)
    df2 = get_historical_klines(
        client,
        symbol,
        startTime=int(start_time.timestamp() * 1000),
        endTime=int(end_time.timestamp() * 1000)
    )

    result_df = pd.concat([df1, df2], ignore_index=True)
    result_df = result_df.sort_values(by='Time')
    result_df = result_df.drop_duplicates(subset='Time', keep='last')
    result_df.reset_index(drop=True, inplace=True)
    return result_df


def update_df_klines(client: UMFutures, symbol: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(f"binance_utils/data_frames_csv/{symbol}.csv")
        end_time = datetime.strptime(df['Time'].iloc[-1], "%Y-%m-%d %H:%M:%S")
        limit = ((datetime.utcnow() - end_time).total_seconds()) // (15 * 60)
        new_data_df = get_historical_klines(client, symbol, limit=int(limit+1))
        df['Time'] = pd.to_datetime(df['Time'])
        df = pd.concat([df, new_data_df], ignore_index=True)
        df = df.sort_values(by='Time')
        df = df.drop_duplicates(subset='Time', keep='last')
        df.reset_index(drop=True, inplace=True)
        df.to_csv(f"binance_utils/data_frames_csv/{symbol}.csv", index=False)

    except FileNotFoundError:
        df = get_df_klines_1_month(client, symbol)
        df.to_csv(f"binance_utils/data_frames_csv/{symbol}.csv", index=False)
    return df


def find_levels(df: pd.DataFrame):
    df['Close_MA'] = df['Close'].rolling(window=20).mean()

    maxima_indices, _ = find_peaks(
        x=df['Close_MA'], 
        height=df['Close'].iloc[-1],
        distance=200,
        width=20,
    )

    minima_indices, _ = find_peaks(
        x=-df['Close_MA'], 
        height=-df['Close'].iloc[-1],
        distance=200,
        width=20,
    )

    resistance_lvls = []
    support_lvls = []

    for peaks in reversed(maxima_indices):
        slice_df = df.iloc[peaks-25:peaks+5]
        max_high_idx = slice_df['High'].idxmax()
        data = {
            'idx' : int(max_high_idx),
            'time' : df.loc[max_high_idx, 'Time'],
            'price' : float(df.loc[max_high_idx, 'High'])
        }
        if not resistance_lvls:
            resistance_lvls.append(data)
            continue
        if data['price'] > 1.015 * resistance_lvls[-1]['price']:
            resistance_lvls.append(data)
        
    for peaks in reversed(minima_indices):
        slice_df = df.iloc[peaks-25:peaks+5]
        max_high_idx = slice_df['Low'].idxmin()
        data = {
            'idx' : int(max_high_idx),
            'time' : df.loc[max_high_idx, 'Time'],
            'price' : float(df.loc[max_high_idx, 'High'])
        }
        if not support_lvls:
            support_lvls.append(data)
            continue
        if data['price'] < 0.985 * support_lvls[-1]['price']:
            support_lvls.append(data)
    
    # print('support_lvl\n', support_lvl, '\nresistance_lvl\n', resistance_lvl)
    return (resistance_lvls, support_lvls)


def plot_candlestick_chart(df: pd.DataFrame, symbol, resistance_lvls, support_lvls):
    matplotlib.use('agg')
    plt.clf() 
    plt.plot(df['Time'], df['Close'], label='High')
    for level in resistance_lvls:
        plt.scatter(df['Time'].iloc[level['idx']], df['High'].iloc[level['idx']], color='red', marker='o', label='Вершины')
    for level in support_lvls:
        plt.scatter(df['Time'].iloc[level['idx']], df['Low'].iloc[level['idx']], color='green', marker='o', label='Впадины')

    plt.title(f'График закрытия {symbol} и уровни')
    plt.xlabel('Время')
    plt.ylabel('Цена')
    # форматирование шкалы даты 
    ax = plt.gca()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d')) 
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=5)) 
    # добавление сетки цены
    plt.locator_params(axis='y', nbins=10)
    plt.grid(axis='y', linestyle='--', linewidth=0.5)
    plt.savefig("candlestick_chart.jpg")
    # plt.show()


def update_trading_levels(client: UMFutures, list_working_orders: list, symbol: str) -> list:

    def check_price_existence(price, existing_coin_prices):
        for existing_price in existing_coin_prices:
            if abs(price - existing_price) <= existing_price * 0.005:
                return True
        return False
    
    new_orders = []
    df = update_df_klines(client, symbol)
    resistance_lvls, support_lvls = find_levels(df)
    plot_candlestick_chart(df, symbol, resistance_lvls, support_lvls)
    send_telegram_photo(symbol)
    existing_coin_prices = [order['price'] for order in list_working_orders if order['coin'] == symbol]
    for lvl in resistance_lvls:
        if lvl['price'] not in existing_coin_prices and not check_price_existence(lvl['price'], existing_coin_prices):
            new_orders.append({'coin': symbol, 'price': lvl['price'], 'action': 'SELL'})
    for lvl in support_lvls:
        if lvl['price'] not in existing_coin_prices and not check_price_existence(lvl['price'], existing_coin_prices):
            new_orders.append({'coin': symbol, 'price': lvl['price'], 'action': 'BUY'})
    return new_orders







# if __name__ == '__main__':


# #     symbols = ['BTCUSDT', 'ETHUSDT', 'ATOMUSDT', 'NEARUSDT', 'SOLUSDT', 'BNBUSDT', 'SUIUSDT']
# #     for symbol in symbols:
# #         # symbol = "FOOTBALLUSDT"
# #         df = update_df_klines(client, symbol)
# #         resistance_lvl, support_lvl = find_levels(df)
# #         plot_candlestick_chart(df, resistance_lvl, support_lvl)
# #         send_telegram_photo(symbol)
# #         time.sleep(2)
    
#     symbol = "FOOTBALLUSDT"
#     df = update_df_klines(client, symbol)
#     resistance_lvl, support_lvl = find_levels(df)
#     plot_candlestick_chart(df, resistance_lvl, support_lvl)
#     send_telegram_photo(symbol)
