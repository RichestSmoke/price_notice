from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
    )


main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Добавить ордер")
        ],
        [
            KeyboardButton(text="Посмотреть ордеры"),
            KeyboardButton(text="Удалить ордеры")
        ],
        [
            KeyboardButton(text="Мониторинг")
        ]
    ],
    resize_keyboard=True
)

cancel_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Отмена")
        ]
    ],
    resize_keyboard=True
)

del_order_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Удалить ордер")
        ],
        [
            KeyboardButton(text="Удалить монету"),
            KeyboardButton(text="Удалить все ордера")
        ],
        [
            KeyboardButton(text='Отмена')
        ]
    ],
    resize_keyboard=True
)

monitoring_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="BinanceWebsocketMarkPrice")
        ],
        [
            KeyboardButton(text="BinanceWebsocketUserData")
        ],
        [
            KeyboardButton(text="Отмена")
        ]
    ],
    resize_keyboard=True
)