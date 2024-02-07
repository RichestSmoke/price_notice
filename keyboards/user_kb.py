from aiogram.types import (
    ReplyKeyboardMarkup, 
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup
    )


main_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Добавить ордер/торговую пару")
        ],
        [
            KeyboardButton(text="Посмотреть ордеры"),
            KeyboardButton(text="Удалить ордеры")
        ],
        [
            KeyboardButton(text="Мониторинг"),
            KeyboardButton(text="Config")
        ]
    ],
    resize_keyboard=True
)


add_order_or_pair_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Добавить ордер"),
        ],
        [
            KeyboardButton(text="Добавить торговую пару"),
        ],
        [
            KeyboardButton(text="Отмена")
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
            KeyboardButton(text="WebsocketMarkPrice"),
            KeyboardButton(text="WebsocketUserData")
        ],
        [
            KeyboardButton(text="is_open_position_dict")
        ],
        [
            KeyboardButton(text="Отмена")
        ]
    ],
    resize_keyboard=True
)