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
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, BufferedInputFile, BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder

import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib as mpl
mpl.style.use('ggplot')

# --- Конфигурация ---
TOKEN = os.getenv("BOT_TOKEN", "8869229955:AAEddtB8es48kh92WU48vVBbu6-6dFrgeKk")

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

    #обработка повторяющихся названий колонок
    cols_ = df.iloc[0].astype('str').to_list()
    cols_unique = []
    counter = {}
    df.iloc[0]
    for col in cols_:
        if col in cols_unique:
            counter[col] += 1
            cols_unique.append(f'{col}.{counter[col]}')
        else:
            counter[col] = 0
            cols_unique.append(col)

    df_basic.columns = cols_unique
    df_basic = df_basic[1:].reset_index(drop=True)
    #Определеяем колонку "Дата" как новый индекс в формате datetime
    df_basic['Дата'] = pd.to_datetime(df_basic['Дата'], format='%d.%m.%Y', errors="coerce")
    df_basic = df_basic.dropna(subset=['Дата']) 
    df_basic = df_basic.set_index('Дата')

    return df_basic

# --- Получение данных со всего листа текущего месяца
def get_sample_data():
    sheet = client.open_by_key('1o1mIcsXQht1NFhgsq7CMKI3derC8xOSrRgGC9GYu144').worksheet(f'{month} {year}')
    return prepare(sheet)

# --- Получение данных со всего листа прошлого месяца ---
def get_sample_data_past_month():
    sheet = client.open_by_key('1o1mIcsXQht1NFhgsq7CMKI3derC8xOSrRgGC9GYu144').worksheet(f'{past_month} {year}')
    return prepare(sheet)

# --- Выделяем отдельно данные от Я.метрик, скармливая в функцию весь текущий или предыдущий месяц ---
def get_ya_metrik(all_data):
    return all_data.iloc[:, :10][['номер недели', 'Трафик', 'Уникальные', 'vs LY', 'Переход в каталог', 'Положил в корзину', 'Оформил заказ']]

# --- Выделяем отдельно данные о продажах
def get_sales_data(all_data):
    return all_data[['План Руб', 'План Заказы', 'Заказы Сайт, шт', 'Сумма заказов РУБ']]

# --- Выделяем отдельно регистрациях
def get_reg_info(all_data):
    return all_data[['ШТ', 'vs LY.1']]

# --- Выделяем отдельно продажах сертификатов
def get_cert_info(all_data):    
    return all_data[['Сертификаты, шт', 'Сертификаты, Руб']]



# --- Генерация графика и возврат файла-объекта ---
def generate_chart_bytes(df):

    fig, axes = plt.subplots(2,1, figsize=(12,14), sharex=True)

    days = pd.to_datetime(df.index, format='%d.%m.%Y').day

    sns.lineplot(x=days, y=df['CTR_to_catalog'], label='CTR в каталог', 
                 ax=axes[0], color='#1f77b4', linewidth=2.5, marker='o')
    sns.lineplot(x=days, y=df['CTR_to_basket'], label='CTR в корзину', 
                 ax=axes[0], color="#1fb451", linewidth=2.5, marker='o')
    sns.lineplot(x=days, y=df['CTR_to_order'], label='CTR в заказ', 
                 ax=axes[0], color="#b4991f", linewidth=2.5, marker='o')
    axes[0].set_title(f'CTR за {past_month}', fontsize=14, fontweight='bold', pad=10)
    axes[0].set_ylabel('Проценты, %', fontsize=12)
    axes[0].legend(loc='upper right')


    sns.lineplot(x=days, y=df['Уникальные'], 
                 ax=axes[1], color="#1a3a42", linewidth=2.5, marker='o')
    axes[1].set_title(f'Трафик Уникальные за {past_month}', fontsize=14, 
                      fontweight='bold', pad=10)
    axes[1].set_ylabel('Пользователи, чел.', fontsize=12)
    axes[1].set_xlabel('День месяца', fontsize=12)

    axes[1].set_xticks(days) 
    axes[1].set_xticklabels(days, rotation=45)
    
    
    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf.read()




def generate_chart2_bytes(df):
    days = pd.to_datetime(df.index, format='%d.%m.%Y').day
    fig, ax = plt.subplots(figsize=(10, 18))

    sns.barplot(y=days, x=df['План Руб'], orient='h',
                color="#05548d", width=0.8, ax=ax, label='План')
    fact_bars = sns.barplot(y=days, x=df['Сумма заказов РУБ'], orient='h',
                color="#9cc2dd", width=0.6, ax=ax, label='Факт')

    ax.set_title(f'График выполнения плана в {past_month}', 
                 fontsize=14, fontweight='bold', pad=15)
    ax.set_ylabel('День месяца', fontsize=12)
    ax.set_xlabel('Руб.', fontsize=12)

    ax.set_yticks(range(len(days))) 
    ax.set_yticklabels(days, rotation=0)
    ax.legend(loc='lower right')

    labels = [f"{val:.1f}%" if pd.notna(val) else "0%" for val in df['percentage']]
    container = ax.containers[-1] 

    ax.bar_label(container=container, labels=labels,
                 label_type='center', color='black',       
                 fontsize=9, fontweight='bold')
    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf.read()





# ---------- Функции меню и основных команд
async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command='/start', description='❗Запустить бота / Главное меню'),
        BotCommand(command='/help', description='❓Помощь и описание кнопок')
    ]
    await bot.set_my_commands(main_menu_commands)

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

# --- Обработчик: открытие подменю графиков
@router.callback_query(F.data == "show_chart")
async def cb_charts_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "Выберите тип графика:",
        reply_markup=chart_keyboard(),
    )
    await callback.answer()      

# ---Обработчик: Возврат в главное меню
@router.callback_query(F.data == "back_to_main")
async def cb_back_to_main(callback: CallbackQuery):
    if callback.message.photo:
        
        await callback.message.edit_reply_markup(reply_markup=None)
        
        # Отправляем главное меню новым сообщением ниже
        await callback.message.answer(
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

# --- Функция для формирования текста выдачи статистики по продажам
def text_func(line):
    if pd.isna(line['Сумма заказов РУБ']):
        return f'За {line.name.strftime('%d.%m.%Y')} нет данных'
    else:
        return (f"{line.name.strftime('%d.%m.%Y')}:\n"
                 f"🔵Доля выполнения плана на день: {line['Доля']:.2%}\n"
                 f"🔵Ср. чек: {line['Ср. чек']:.0f} руб.\n"
                 f"🔵CR оформленных заказов: {line['CTR оплаченного заказа']}")

        
# --- Обработчик: Статистика продаж
@router.callback_query(F.data == 'stats:sales')
async def stats_sales(callback: CallbackQuery):
    raw_df = await asyncio.to_thread(get_sample_data)
    df = get_sales_data(raw_df)

    # Получаем данные по продажам в этом месяце за последние 5 дней
    df = df.replace(r'^\s*$', None, regex=True)
    end_date = pd.to_datetime(full_date, format='%d.%m.%Y')
    start_date = end_date - timedelta(days=4)
    last_sales_rows = df.loc[start_date:end_date].copy() 
    '''if end_date.day < 5:
        start_date = end_date.replace(day=1)
        last_sales_rows = df.loc[start_date:end_date].copy()'''        
     

    df_ = get_ya_metrik(raw_df).loc[last_sales_rows.index]
    df_result = pd.concat([last_sales_rows, df_],axis=1)

    # Вновь убираем лишние пробелы из всех строк таблицы и переводим данные в числовой формат
    df_result = df_result.astype(str).replace(r'\s+', '', regex=True)
    df_result = df_result.apply(pd.to_numeric, errors='coerce')

    df_result['CTR оплаченного заказа'] = round(df_result['Оформил заказ']/ df_result['Заказы Сайт, шт'], 2) *100
    df_result['CTR оплаченного заказа'] = df_result['CTR оплаченного заказа'].astype('str')+'%'
    df_result['CTR оплаченного заказа'] = df_result['CTR оплаченного заказа'].replace('nan%', 'нет данных')
    df_result['Доля'] = df_result['Сумма заказов РУБ']/ df_result['План Руб'] 
    df_result['Ср. чек'] = df_result['Сумма заказов РУБ']/ df_result['Заказы Сайт, шт']
    df_result['Ср. чек'] = pd.to_numeric(df_result['Ср. чек'],errors='coerce').astype('float32')

    lines = df_result.apply(lambda X: text_func(X), axis=1)
    text = "\n\n".join(lines)

    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer


# --- Обработчик: Данные за текущий месяц
@router.callback_query(F.data == 'stats:current_month')
async def stats_current_month(callback: CallbackQuery):    
    raw_df = await asyncio.to_thread(get_sample_data)
    raw_df = raw_df[['Трафик', 'Уникальные', 'vs LY', 'Переход в каталог', 'Положил в корзину', 'Оформил заказ',
                'План Руб', 'План Заказы', 'Заказы Сайт, шт', 'Сумма заказов РУБ']]
    raw_df = raw_df.astype(str).replace(r'\s+', '', regex=True)
    raw_df = raw_df.apply(pd.to_numeric, errors='coerce')
    #raw_df = raw_df.iloc[:-1, :]

    Sales_goal_current = raw_df['План Руб'].sum()   

    
    if raw_df[~raw_df['Сумма заказов РУБ'].isna()].shape[0] == 0:
        
        text = f'🔴Данные на {full_date} отсутствуют с начала месяца'
            
    else:
        CTR_to_pay = raw_df['Заказы Сайт, шт'].sum()/ raw_df['Уникальные'].sum()
        raw_df['AVG_check'] = raw_df['Сумма заказов РУБ']/ raw_df['Заказы Сайт, шт']
        count_of_days = int(raw_df.index[-1].day)        
        rest_days = count_of_days - int(raw_df[~raw_df['Сумма заказов РУБ'].isna()].index[-1].day)
        predict = raw_df['Сумма заказов РУБ'].mean() * count_of_days
        stg = (Sales_goal_current - raw_df['Сумма заказов РУБ'].sum())/ rest_days   #sales_per_day_to_goal

        last_date = raw_df[~raw_df['Сумма заказов РУБ'].isna()].index[-1].strftime('%d.%m.%Y')
        text = f'Данные на {last_date}:\n\
        🔴Сумма продаж в тек. месяце: {raw_df['Сумма заказов РУБ'].sum():,.2f} руб.\n\
        🔴План: {float(Sales_goal_current)} руб.\n\
        🔴Средний чек: {raw_df['AVG_check'].mean():,.2f} руб.\n\
        🔴CTR продажа-показ: {CTR_to_pay:,.2f}%\n\
        🔴Факт. выполнение: {(100*raw_df['Сумма заказов РУБ'].sum()/Sales_goal_current):,.2f}%\n\
        🔴Прогноз продаж: {predict:,.2f}руб - {100*(predict/Sales_goal_current):,.2f}%\n\
        🔴Необходимые продажи в день: {stg:,.2f} руб.'

    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer
       

# --- Обработчик: Данные за прошедший месяц
@router.callback_query(F.data == 'stats:last_month')
async def stats_past_month(callback: CallbackQuery):    
    raw_df = await asyncio.to_thread(get_sample_data_past_month)
    raw_df = raw_df[['Трафик', 'Уникальные', 'vs LY', 'Переход в каталог', 'Положил в корзину', 'Оформил заказ',
                'План Руб', 'План Заказы', 'Заказы Сайт, шт', 'Сумма заказов РУБ', 'ШТ', 'vs LY.1',  'Сертификаты, шт', 'Сертификаты, Руб']]
    raw_df = raw_df.astype(str).replace(r'\s+', '', regex=True)
    raw_df = raw_df.apply(pd.to_numeric, errors='coerce')

    Sales_goal_prev = raw_df['План Руб'].sum()
    CTR_to_pay = raw_df['Заказы Сайт, шт'].sum()/ raw_df['Уникальные'].sum()
    raw_df['AVG_check'] = raw_df['Сумма заказов РУБ']/ raw_df['Заказы Сайт, шт']
    

    df_reg = get_reg_info(raw_df)
    df_reg = df_reg[~df_reg['ШТ'].isna()]
    dif_reg = 100 * (df_reg['ШТ'].sum()/ df_reg['vs LY.1'].sum())
    ldr_date = df_reg.index[-1].strftime('%d.%m.%Y') # Последняя доступная дата информации по регистрациям
    df_cert = get_cert_info(raw_df)
    df_cert = df_cert[~df_cert['Сертификаты, шт'].isna()]
    ldc_date = df_cert.index[-1].strftime('%d.%m.%Y')

        
    text = f'Данные за {past_month} {year}г.:\n\
    🔵Сумма продаж: {raw_df['Сумма заказов РУБ'].sum():,.2f} руб.\n\
    🔵План: {(Sales_goal_prev)} руб.\n\
    🔵Средний чек: {raw_df['Сумма заказов РУБ'].sum()/ raw_df['Заказы Сайт, шт'].sum():,.2f} руб.\n\
    🔵CTR продажа-показ: {100*CTR_to_pay:,.2f}%\n\
    🔵Выполнен план на {(100*raw_df['Сумма заказов РУБ'].sum()/Sales_goal_prev):,.1f}%\n\
    🔵Регистрации от прошлогодних на {ldr_date}: {dif_reg:,.2f}%\n\
    🔵На {ldc_date} продано {int(df_cert['Сертификаты, шт'].sum())} сертификатов на {df_cert['Сертификаты, Руб'].sum():,.2f} руб.'
    
    await callback.message.edit_text(text, reply_markup=stats_keyboard())
    await callback.answer



# --- Обработчик: График 1
@router.callback_query(F.data == 'chart:chart1')
async def chart_lineplot_ya_metics(callback: CallbackQuery):
    raw_df = await asyncio.to_thread(get_sample_data_past_month)
    df = get_ya_metrik(raw_df)

    df = df.astype(str).replace(r'\s+', '', regex=True)
    df = df.apply(pd.to_numeric, errors='coerce')

    df['CTR_to_catalog'] = 100 * df['Переход в каталог']/ df['Уникальные']
    df['CTR_to_basket'] = 100 * df['Положил в корзину']/ df['Уникальные']
    df['CTR_to_order'] = 100 * df['Оформил заказ']/ df['Уникальные']

    chart_bytes = generate_chart_bytes(df)
    photo = BufferedInputFile(chart_bytes, filename="chart_ctr.png")

    await callback.message.answer_photo(
        photo=photo,
        caption=f"📈 Графики трафика и конверсии за {past_month}",
        reply_markup=chart_keyboard()
    )



# --- Обработчик: График 2
@router.callback_query(F.data == 'chart:chart2')
async def chart_lineplot_sales_metics(callback: CallbackQuery):
    raw_df = await asyncio.to_thread(get_sample_data_past_month)
    df = get_sales_data(raw_df)
    
    df = df.astype(str).replace(r'\s+', '', regex=True)
    df = df.apply(pd.to_numeric, errors='coerce')
    df['Сумма заказов РУБ'] = df['Сумма заказов РУБ'].fillna(0)

    df['percentage'] = 100 * df['Сумма заказов РУБ']/ df['План Руб'] + 1e-9

    chart_bytes = generate_chart2_bytes(df)
    photo = BufferedInputFile(chart_bytes, filename="chart_ctr.png")
    
    await callback.message.answer_photo(
        photo=photo,
        caption=f"💰 График выполнения плана продаж за {past_month}",
        reply_markup=chart_keyboard()
    )




# ---------- Клавиатуры---------
# --- Главная клава
def main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Показать график продаж", callback_data="show_chart")
    builder.button(text="📋 Статистика", callback_data="stats_menu")
    return builder.as_markup()


# --- Подменю графиков
def chart_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 График1", callback_data="chart:chart1")
    builder.button(text="💰 График2", callback_data="chart:chart2")
    builder.button(text="⬖️ Назад", callback_data="back_to_main")
    builder.adjust(2, 1)  
    return builder.as_markup() 


# --- Подменю статистики
def stats_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Я.метрики", callback_data="stats:metrics")
    builder.button(text="💰 Продажи", callback_data="stats:sales")
    builder.button(text="⬅️ Прошлый месяц", callback_data="stats:last_month")
    builder.button(text="⏳ Текущий месяц", callback_data="stats:current_month")
    builder.button(text="⬖️ Назад", callback_data="back_to_main")
    builder.adjust(1)  
    return builder.as_markup()



# --- Запуск 
async def main():
    await set_main_menu(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())





