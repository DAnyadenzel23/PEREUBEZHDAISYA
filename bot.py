import os
import asyncio
from io import BytesIO

import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

from datetime import datetime as dt
from datetime import timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

import matplotlib.pyplot as plt


# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN", "8529846135:AAEz1MzQtR_QL2SItlt073gnwX0ntgit5dg")

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)




# --- Подключение к гугл таблице и определение текущей даты
scopes = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

creds = Credentials.from_service_account_file('credentials.json', scopes=scopes)
client = gspread.authorize(creds)

yesterday = dt.today() - timedelta(days=1) #Определяем дату предыдущего дня
months_dict = {
    1: "Январь",
    2: "Февраль",
    3: "Март",
    4: "Апрель",
    5: "Май",
    6: "Июнь",
    7: "Июль",
    8: "Август",
    9: "Сентябрь",
    10: "Октябрь",
    11: "Ноябрь",
    12: "Декабрь"
}
year = yesterday.year
month = months_dict.get(yesterday.month)
day = yesterday.day
full_date  = yesterday.strftime('%d.%m.%Y')

key = next((k for k, v in months_dict.items() if v == month), None)
past_month = months_dict.get(key - 1) # Закрепляем в переменную значение предыдущего месяца


# --- Вспомогательная функция для предподготовнки табличных данных
def prepare(sheet):
    data = sheet.get_all_values()
    df = pd.DataFrame(data)
    df = df.loc[3:]
    df_basic = df.copy()
    df_basic.columns = df.iloc[0]
    df_basic = df_basic[1:].reset_index(drop=True)
    #Определеяем колонку "Дата" как новый индекс в формате datetime
    df_basic['Дата'] = pd.to_datetime(df_basic['Дата'], format='%d.%m.%Y', errors="coerce")
    df_basic = df_basic.dropna(subset=['Дата']) 
    df_basic = df_basic.set_index('Дата')

# --- Получение данных со всего листа текущего месяца ---
def get_sample_data():
    sheet = client.open_by_key('1o1mIcsXQht1NFhgsq7CMKI3derC8xOSrRgGC9GYu144').worksheet(f'{month} {year}')
    return prepare(sheet)

# --- Получение данных со всего листа прошлого месяца ---
def get_sample_data_past_month():
    sheet = client.open_by_key('1o1mIcsXQht1NFhgsq7CMKI3derC8xOSrRgGC9GYu144').worksheet(f'{past_month} {year}')
    return prepare(sheet)

# --- Выделяем отдельно данные от Я.метрик, скармливая в функцию весь текущий или предыдущий месяц ---
def get_ya_metrik(all_data):
    return all_data().iloc[:, :10][['номер недели', 'Трафик', 'Уникальные', 'vs LY', 'Переход в каталог', 'Положил в корзину', 'Оформил заказ']]

# --- Выделяем отдельно данные о продажах
def get_sales_data(all_data):
    return all_data()[['План Руб', 'План Заказы', 'Заказы Сайт, шт', 'Сумма заказов РУБ']]


'''# --- Генерация графика и возврат файла-объекта ---
def generate_chart_bytes(df: pd.DataFrame) -> bytes:
    plt.figure(figsize=(6, 4), dpi=150)
    plt.plot(df["date"], df["sales"], marker="o", linewidth=2, markersize=4)
    plt.title("Продажи по дням")
    plt.xlabel("Дата")
    plt.ylabel("Сумма, ₽")
    plt.grid(True, linestyle="--", alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf.read()'''




@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот для аналитики...",
        reply_markup=main_keyboard(),
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
            "Объяснение кнопок",
            reply_markup=main_keyboard(),
        )
    
# --- Обработчик: открытие подменю статистики
@router.callback_query(F.data == "stats_menu")
async def cb_stats_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите тип статистики по последней доступной для нее дате или общую за текущий/прошлый месяц:",
        reply_markup=stats_keyboard(),
    )
    await callback.answer() 

# ---Обработчик: Возврат в главное меню
@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "Главное меню. Выберите действие:",
        reply_markup=main_keyboard(),
    )
    await callback.answer()

# --- Обработчик: Базовая статистика по яндекс метрикам за прошлый день(последний доступный)
@router.callback_query(F.data == 'stats:metrics')
async def stats_ya_metrics(callback: CallbackQuery):
    raw_df = await asyncio.to_thread(get_sample_data)
    df = get_ya_metrik(raw_df)
    # Получаем  данные от Я.метрик за прошедшую дату
    prev_date = pd.to_datetime(full_date, format='%d.%m.%Y')
    day_ya_info = df.loc[prev_date]

    day_ya_info = (day_ya_info.astype('str')  
                        .str.replace(r'\s+', '', regex=True)
                        .astype('float32')) # Убираем лишние пробелы во всей таблице и переводим строчные даннын в числовые
    traffic_vs_LY = 100 * day_ya_info['Уникальные']/day_ya_info['vs LY']
    CTR_to_catalog = 100 * day_ya_info['Переход в каталог']/day_ya_info['Уникальные']
    CTR_to_basket = 100 * day_ya_info['Положил в корзину']/day_ya_info['Уникальные']
    CTR_to_order = 100 * day_ya_info['Оформил заказ']/day_ya_info['Уникальные']
    
    text = f'Данные за {full_date}:\n\
    🟢трафик от прошлогоднего: {traffic_vs_LY:,.2f}%\n\
    🟢CTR перехода в каталог: {CTR_to_catalog:,.2f}%\n\
    🟢CTR добавления в корзину: {CTR_to_basket:,.2f}%\n\
    🟢CTR создания заказа: {CTR_to_order:,.2f}%'
    
    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer()           

@router.callback_query(F.data == 'stats:sales')
async def stats_sales(callback: CallbackQuery):
    raw_df = await asyncio.to_thread(get_sample_data)
    df = get_sales_data(raw_df)

    # Получаем данные по продажам в этом месяце за последние 5 дней
    df = df.replace(r'^\s*$', None, regex=True)
    sales_df = df.dropna(subset=['Сумма заказов РУБ'])
    last_sales_rows = sales_df.iloc[-1:-6]

    last_sales_rows['Доля'] = last_sales_rows['Сумма заказов РУБ']/ df_sales_last5['План Руб'] 
    last_sales_rows['Ср. чек'] = last_sales_rows['Сумма заказов РУБ']/ df_sales_last5['Заказы Сайт, шт']
    last_sales_rows = last_sales_rows.fillna('нет данных')

    df_ = get_ya_metrik(raw_df).loc[last_sales_rows.index]
    df_result = pd.merge(last_sales_rows, df_,)




# ---------- Клавиатуры---------
# --- Главная клава
def main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Показать график продаж", callback_data="show_chart")
    builder.button(text="📋 Статистика", callback_data="stats_menu")
    return builder.as_markup()
# --- Подменю статистики
def stats_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Я.метрики", callback_data="stats:metrics")
    builder.button(text="💰 Продажи", callback_data="stats:sales")
    builder.button(text="⬅️ Прошлый месяц", callback_data="stats:last_month")
    builder.button(text="⏳ Текущий месяц", callback_data="stats:current_month")
    builder.button(text="⬅ Назад", callback_data="back_to_main")
    builder.adjust(1)  
    return builder.as_markup()



# --- Запуск 
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





