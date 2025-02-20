from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from keyboards.user_kb import (
    main_kb, 
    cancel_kb, 
    del_order_kb, 
    monitoring_kb,
    add_order_or_pair_kb
    )
from utils.states import (
    NewNoticeState, 
    DeleteNoticeState,
    ConficTradeState
)
from utils.validation import check_input_notice_data, string_to_list
from utils.mongodb import (
    update_data_on_db,
    show_data_in_db,
    remove_object_from_coin,
    remove_data_for_coin,
    clear_entire_collection 
    )
from trading_bot import (
    ticker_and_price_dict,
    list_working_orders,
    last_order,
    trading_cnfg,
    client,
    is_open_position_dict,
    update_trading_levels

)
import json


router = Router()
ADMIN = 425136998


@router.message(CommandStart())
async def send_welcom(message: Message):
    await message.answer(
        f"Привет {message.from_user.first_name}!\n"
        "Этот бот создан для уведомления цен на Binance Futures.\n"
        "Для использования бота обратитесь к админу @seventeene",
        reply_markup=main_kb
    )


@router.message(F.text == "Отмена")
async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Главное меню", reply_markup=main_kb)


@router.message(F.text == "Добавить ордер/торговую пару")
async def add_order_or_pair_handler(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN:
        await state.set_state(NewNoticeState.enter_data)
        await message.answer(
            "▪ Добавить один или несколько ордеров\n"
            "▪ Добавить торговую пару для рассчета уровней",
            reply_markup=add_order_or_pair_kb
        )
    else:
        await message.answer("Нет доступа!", reply_markup=main_kb)



@router.message(F.text == "Добавить ордер")
async def new_notice(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN:
        await state.set_state(NewNoticeState.add_order)
        await message.answer(
            "Введите уведомление в формате:\n"
            "❗️Цена должна быть со знаком .\n"
            "❗️Ордеры должны быть разделенными знаком ,\n"
            "BTC-35000.00-S\n"
            "BTC-35000.00-S,BTC-2400.5-B",
            reply_markup=cancel_kb
        )
    else:
        await message.answer("Нет доступа!", reply_markup=main_kb)
    


@router.message(NewNoticeState.add_order)
async def writing_new_notice(message: Message, state: FSMContext):
    text_data_orders = string_to_list(message.text)
    new_orders_list = []
    message_text = "Принято!\n"
    for order in text_data_orders:
        if check_input_notice_data(order):
            order_split = order.split('-')
            order_data = {
                'coin' : f"{order_split[0].upper()}USDT",
                'price' : float(order_split[1]),
                'action' : 'BUY' if order_split[2].upper() in ('B', 'BUY') else 'SELL'
            }
            new_orders_list.append(order_data)
            message_text += f"{order_data['coin']} -- ${order_data['price']}  {order_data['action']}\n"
        
        else:
            await message.answer(
            "Не правильный формат!\n"
            f"Итерация прервалась на этой части: {order}\n"
            "❗️Проверьте название монеты нужно вписывать без USDT\n"
            "❗️Цена должна быть десятичным числом со знаком .\n"
            "❗️Действие может быть только B - buy или S - short\n"
            "❗️Между монетой, ценой и действием должен стоять знак '-'\n"
            "❗️Не использовать пробелов"
        )
            return

    list_working_orders.extend(new_orders_list)
    result_update_db = await update_data_on_db(new_orders_list)
    message_text += f"db_result:\n{result_update_db}"
    await state.clear()
    await message.reply(message_text, reply_markup=main_kb)



@router.message(F.text == "Добавить торговую пару")
async def add_trading_pair_handler(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN:
        await state.set_state(NewNoticeState.add_pair)
        await message.answer(
            "Введите символ в формате:\n"
            "BTCUSDT",
            reply_markup=cancel_kb
        )
    else:
        await message.answer("Нет доступа!", reply_markup=main_kb)



@router.message(NewNoticeState.add_pair)
async def process_add_trading_pair_handler(message: Message, state: FSMContext):
    await state.clear()
    symbol = message.text.upper()
    if not symbol.endswith('USDT'):
        symbol += 'USDT'
    if symbol in ticker_and_price_dict:
        with open('trading_pair.json', 'r+') as file:
            coins_list = json.load(file)
            coins_dict = {item: None for item in coins_list}
            if symbol not in coins_dict:
                coins_dict[symbol] = None
            coins_list = list(coins_dict.keys())
            file.seek(0)
            json.dump(coins_list, file)
            file.truncate()
        list_working_orders_copy = list_working_orders.copy()
        new_orders = update_trading_levels(client, list_working_orders_copy, symbol)
        db_result = await update_data_on_db(new_orders)
        list_working_orders.extend(new_orders)
        text = ""
        for order in new_orders:
            text += f"{order['coin']}  -  {order['price']}$ {order['action']}\n"
        await message.reply(
            f"{symbol} успешно сохранен, новые ордера:\n"
            f"{text}"
            f"db: {db_result}", 
            reply_markup=main_kb)
    else:
        await message.reply(f"Пары {symbol} нет в словаре ticker_list", reply_markup=main_kb)



@router.message(F.text == "Посмотреть ордеры")
async def show_notice(message: Message):
    notice_data = await show_data_in_db()
    answer_text = ""
    for order in notice_data:
        try:
            delta_precent = ((order['price'] - ticker_and_price_dict[order['coin']]) / ticker_and_price_dict[order['coin']]) * 100
            answer_text += (
                f"{order['coin']} -- ${order['price']} {'⬇' if order['action'] == 'SELL' else '⬆'} "
                f"{'🔴' if abs(delta_precent) <= 1 else ('🟠' if 1 < abs(delta_precent) < 7 else '🟢')} {round((delta_precent), 1)}%\n"
            )
        except:
            answer_text += f"{order['coin']}  --  нет такой монеты!"
    answer_text += f"Всего {len(notice_data)} ордеров"
    await message.answer(answer_text)


@router.message(F.text == "Удалить ордеры")
async def del_notice(message: Message, state: FSMContext):
    if message.from_user.id == ADMIN:
        await state.set_state(DeleteNoticeState.start_del)
        await message.answer("Выберите что удалить:", reply_markup=del_order_kb)
    else:
        await message.answer("Нет доступа!", reply_markup=main_kb)



@router.message(F.text == "Удалить ордер")
async def del_order_handler(message: Message, state: FSMContext):
    if await state.get_state() == DeleteNoticeState.start_del.state:
        await state. set_state(DeleteNoticeState.order_del)
        message_text = "list_working_orders:\n"
        for order in list_working_orders:
            message_text += f"{order['coin'][:-4]}-{order['price']}-{order['action']}\n"
        message_text += f"Всего {len(list_working_orders)} ордеров"
        await message.answer(message_text)
        await message.answer(
        "Введите ордер который хотите удалить в формате:\n"
        "BTC-35000.00-S",
        reply_markup=cancel_kb
    )
        

@router.message(DeleteNoticeState.order_del)
async def feel_del_order_handler(message: Message, state: FSMContext):
    if check_input_notice_data(message.text):
        data = message.text.split("-")
        del_notice_data = {
            'coin' : f"{data[0].upper()}USDT",
            'price' : float(data[1]),
            'action' : 'BUY' if data[2].upper() in ('B', 'BUY') else 'SELL'
        }
        result_update = await remove_object_from_coin(
            del_notice_data['coin'],
            del_notice_data['price'],
            del_notice_data['action']
        )
        list_working_orders.remove(del_notice_data)
        await state.clear()
        await message.reply(
            "Удалено!\n"
            f"coin = {del_notice_data['coin']}, price = {del_notice_data['price']}, "
            f"action = {del_notice_data['action']}, db={result_update}",
            reply_markup=main_kb
        )

    else:
        await message.answer(
            "Не правильный формат!\n"
            "❗️Проверьте название монеты нужно вписывать без USDT\n"
            "❗️Цена должна быть десятичным числом со знаком .\n"
            "❗️Действие может быть только B - buy или S - short\n"
            "❗️Между монетой, ценой и действием должен стоять знак '-'\n"
        )


@router.message(F.text == "Удалить монету")
async def del_coin_handler(message: Message, state: FSMContext) -> None:
    if await state.get_state() == DeleteNoticeState.start_del.state:
        await state. set_state(DeleteNoticeState.coin_del)
        await message.answer(
            "Введите название монеты которую хотите удалить",
            reply_markup=cancel_kb
        )


@router.message(DeleteNoticeState.coin_del)
async def del_coin_handler(message: Message, state: FSMContext) -> None:
    coin = message.text.upper()
    message_text = ""
    order_count = 0
    if not coin.endswith('USDT'):
        coin += 'USDT'
    orders_copy = list(list_working_orders)
    for order in orders_copy:
        if coin == order['coin']:
            message_text += f"{order['coin']}-{order['price']}-{order['action']}\n"
            order_count += 1
            list_working_orders.remove(order)
    result_db = await remove_data_for_coin(coin)
    message_text += f"Всего удалено {order_count} ордеров, db={result_db}"
    with open('trading_pair.json', 'r+') as file:
            coins_list: list = json.load(file)
            if coin in coins_list:
                coins_list.remove(coin)
            file.seek(0)
            json.dump(coins_list, file)
            file.truncate()
    await state.clear()
    await message.answer(
        message_text,
        reply_markup=main_kb
    )


@router.message(F.text == "Удалить все ордера")
async def del_coin_handler(message: Message, state: FSMContext) -> None:
    if await state.get_state() == DeleteNoticeState.start_del.state:
        await state. set_state(DeleteNoticeState.db_del)
        await message.answer(
            "Введите «ПОДТВЕРДИТЬ» если хотите удалить все ордера",
            reply_markup=cancel_kb
        )


@router.message(DeleteNoticeState.db_del)
async def del_coin_handler(message: Message, state: FSMContext) -> None:
    list_working_orders.clear()
    result_db = await clear_entire_collection()
    await state.clear()
    await message.answer(
        f"Все ордера были удалены, db={result_db}",
        reply_markup=main_kb
    )


@router.message(F.text == "Мониторинг")
async def monitoring_handler(message: Message) -> None:
    await message.answer("Что показать?", reply_markup=monitoring_kb)


@router.message(F.text == "WebsocketMarkPrice")
async def show_mark_price_handler(message: Message):
    await message.answer(
        f"BTCUSDT - ${ticker_and_price_dict.get('BTCUSDT')}\n"
        f"ETHUSDT - ${ticker_and_price_dict.get('ETHUSDT')}\n"
        f"SOLUSDT - ${ticker_and_price_dict.get('SOLUSDT')}",
        reply_markup=monitoring_kb
    )


@router.message(F.text == "WebsocketUserData")
async def show_user_data_handler(message: Message) -> None:
    if last_order:
        await message.answer(
            f"pair: {last_order['pair']}\n"
            f"side: {last_order['side']}\n"
            f"average_price: {last_order['average_price']}\n"
            f"order_status: {last_order['order_status']}\n"
            f"realized_profit_of_the_trade: {last_order['realized_profit_of_the_trade']}",
            reply_markup=monitoring_kb
        )
    else:
        await message.answer(
            "Нет данных",
            reply_markup=monitoring_kb
        )


@router.message(F.text == "is_open_position_dict")
async def is_open_position_handler(message: Message) -> None:
    text_messge = ''
    for symbol in is_open_position_dict.keys():
        if is_open_position_dict[symbol]:
            quantity_in_dollar = round(abs(is_open_position_dict[symbol]) * ticker_and_price_dict.get(symbol), 2)
            side = 'BUY' if (is_open_position_dict[symbol] > 0) else 'SELL'
            text_messge += f"{symbol} quantity: {is_open_position_dict[symbol]} = ${quantity_in_dollar} {side}\n"
    if not text_messge:
        text_messge = 'Нет открытых позиций!'
    await message.answer(text_messge, reply_markup=main_kb)


@router.message(F.text == "Config")
async def config_handler(message: Message, state: FSMContext) -> None:
    if message.from_user.id == ADMIN:
        await state.set_state(ConficTradeState.start)
        await message.answer(
            f"\"breakout_strategy\" : {str(trading_cnfg.is_breakout_strategy_enabled).lower()},\n"
            f"\"order_market\" : {str(trading_cnfg.order_market).lower()},\n"
            f"\"position_size\" : {trading_cnfg.position_size_in_dollars},\n"
            f"\"take_price\" : {trading_cnfg.take_price_percentage},\n"
            f"\"stop_price\" : {trading_cnfg.stop_price_percentage},\n"
            f"\"trailing_stop\" : {trading_cnfg.trailing_stop_percent}\n",
            reply_markup=cancel_kb
        )
    else:
        await message.answer("Нет доступа!", reply_markup=main_kb)



@router.message(ConficTradeState.start)
async def recive_config_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    data_string: str = message.text
    data_string = '{' + data_string + '}'
    try:
        cleaned_data_string = data_string.replace('\n', '')
        data_dict = json.loads(cleaned_data_string)
        with open('config.json', 'w') as json_file:
            json.dump(data_dict, json_file)

        trading_cnfg.is_breakout_strategy_enabled = data_dict['breakout_strategy']
        trading_cnfg.order_market = data_dict['order_market']
        trading_cnfg.position_size_in_dollars = data_dict['position_size']
        trading_cnfg.take_price_percentage = data_dict['take_price']
        trading_cnfg.stop_price_percentage = data_dict['stop_price']
        trading_cnfg.trailing_stop_percent = data_dict['trailing_stop']
        await message.reply("Принято!", reply_markup=main_kb)

    except Exception as e:
        error_message = f"Ошибка: {str(e)}"
        await message.reply(error_message, reply_markup=main_kb)

