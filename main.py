from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
from aiogram.utils import markdown, executor
from aiogram.utils.markdown import text, bold, code
from aiogram.utils.emoji import emojize
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
import sqlite3
import locale, datetime

import asyncio
from contextlib import suppress
from aiogram.utils.exceptions import (MessageToEditNotFound, MessageCantBeEdited, MessageCantBeDeleted, MessageToDeleteNotFound)

locale.setlocale(locale.LC_ALL, ('RU', 'utf-8'))
TOKEN = None
with open("token.txt") as f:
    TOKEN = f.read().strip()
bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())


async def delete_message(message: types.Message, sleep_time: int = 0):
    await asyncio.sleep(sleep_time)
    with suppress(MessageCantBeDeleted, MessageToDeleteNotFound):
        await message.delete()
    #asyncio.create_task(delete_message(msg, 0))

@dp.message_handler(Text(equals=['/start','Назад']))
async def cmd_start(message: types.Message):
    connection = sqlite3.connect("botbd.db")
    crsr = connection.cursor()
    kom_tab = str(message.from_user.id) + '_komdb'
    sql_check_table = "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='%s';" %kom_tab
    crsr.execute(sql_check_table)
    for i in crsr.fetchall():
        if (i == (0,)): # No Table Found. Lets create the new one with Telegram User ID name
            sql_create_table = "CREATE TABLE '%s' (ID INTEGER PRIMARY KEY AUTOINCREMENT, YEAR INT(4), MONTH INT(2), ELECTRICITY INT(7), HOT INT(8), COLD INT(8));" %kom_tab
            crsr.execute(sql_create_table)
    starting_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    starting_but1 = emojize(':pencil:')+' Ввести показания за ' + datetime.date.today().strftime("%B %Y").lower()
    starting_but2 = emojize(':chart_increasing:')+' Статистика текущего месяца'
    starting_but3 = emojize(':gear:')+' Настройки'
    starting_kb.add(starting_but1).add(starting_but2).add(starting_but3)
    msg = await message.answer('Привет! 👋\nЭто тестовая версия учета показателей счетчиков.\nИспользуйте кнопки ниже для работы бота.',reply_markup=starting_kb)
    connection.close()

class new_month_states(StatesGroup):
    elec = State()
    hot = State()
    cold = State()
@dp.message_handler(Text(equals=emojize(':pencil:')+' Ввести показания за ' + datetime.date.today().strftime("%B %Y").lower())) # Starting button 1
async def process_elec(message: types.Message):
    connection = sqlite3.connect("botbd.db")
    crsr = connection.cursor()
    kom_tab = str(message.from_user.id) + '_komdb'
    sql_check_month = "SELECT * FROM '%s' WHERE MONTH = '%s' AND YEAR = '%s';" %(kom_tab, datetime.date.today().strftime("%m"), datetime.date.today().strftime("%Y"))
    crsr.execute(sql_check_month)
    if not crsr.fetchall():
        print('empty list: no data about this month')
        await new_month_states.elec.set()
        msg_text = text("Введите показания счетчика:") + "\n" + emojize(':high_voltage:') + bold("Электроэнергия")
        await message.answer(msg_text, reply_markup=types.ReplyKeyboardRemove(),parse_mode=types.ParseMode.MARKDOWN)
    else:
        await message.answer('Показатели за этот месяц уже присутствуют в базе.\nВы можете удалить их в настройках.',parse_mode=types.ParseMode.MARKDOWN)
    connection.close()
@dp.message_handler(lambda message: len(message.text) != 7, state=new_month_states.elec) # Check user input for right answer
@dp.message_handler(lambda message: message.text.isdigit() == False, state=new_month_states.elec)
async def process_elec_invalid(message: types.Message):
    return await message.reply("Некорректные данные.\nВведите все цифры на счетчике\nНапример: 0012345")
@dp.message_handler(state=new_month_states.elec) # Elec answer
async def process_gvs(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['elec'] = message.text
    await new_month_states.next()
    msg_text = text("Введите показания счетчика:") + "\n" + emojize(':thermometer:') + bold("ГВС\n")
    await message.answer(msg_text, parse_mode=types.ParseMode.MARKDOWN)
@dp.message_handler(lambda message: len(message.text) != 8, state=new_month_states.hot) # Check user input for right answer
@dp.message_handler(lambda message: message.text.isdigit() == False, state=new_month_states.hot)
async def process_gvs_invalid(message: types.Message):
    return await message.reply("Некорректные данные.\nВведите все цифры на счетчике\nНапример: 00012345")
@dp.message_handler(state=new_month_states.hot) # gvs answer
async def process_hvs(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['hot'] = message.text
    await new_month_states.next()
    msg_text = text("Введите показания счетчика:") + "\n" + emojize(':ice:') + bold("ХВС")
    await message.answer(msg_text, parse_mode=types.ParseMode.MARKDOWN)
@dp.message_handler(lambda message: message.text.isdigit() == False, state=new_month_states.cold) # Check user input for right answer
@dp.message_handler(lambda message: len(message.text) != 8, state=new_month_states.cold)
async def process_hvs_invalid(message: types.Message):
    return await message.reply("Некорректные данные.\nВведите все цифры на счетчике\nНапример: 00012345")
@dp.message_handler(state=new_month_states.cold) # hvs answer
async def process_sum(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['cold'] = message.text
    await bot.send_message(message.chat.id, markdown.text(
            markdown.text('Ваши показатели за '+datetime.date.today().strftime("%B %Y")+':\n', emojize(':high_voltage: ') + markdown.bold(data['elec'])),
            markdown.text(emojize(':thermometer: ') + markdown.bold(data['hot'])),
            markdown.text(emojize(':ice: ') + markdown.bold(data['cold'])), sep='\n'),parse_mode=types.ParseMode.MARKDOWN)
    connection = sqlite3.connect("botbd.db")
    crsr = connection.cursor()
    kom_tab = str(message.from_user.id) + '_komdb'
    sql_add = 'INSERT INTO "'+kom_tab+'" (YEAR, MONTH, ELECTRICITY, HOT, COLD) VALUES (?,?,?,?,?);'
    crsr.execute(sql_add, (datetime.date.today().strftime("%Y"), datetime.date.today().strftime("%m"), data['elec'], data['hot'], data['cold']))
    connection.commit()
    connection.close()
    await state.finish()  # закончили работать с сотояниями

""" Starting button 2 """
@dp.message_handler(Text(equals=emojize(':chart_increasing:')+' Статистика текущего месяца'))
async def process_month_stats(message: types.Message):
    connection = sqlite3.connect("botbd.db")
    crsr = connection.cursor()
    kom_tab = str(message.from_user.id) + '_komdb'
    sql_check_month = "SELECT * FROM '%s' WHERE MONTH = '%s' AND YEAR = '%s';" %(kom_tab, datetime.date.today().strftime("%m"), datetime.date.today().strftime("%Y"))
    crsr.execute(sql_check_month)
    if not crsr.fetchall():
        await message.answer("Показатели за этот месяц отсутствуют.", reply_markup=types.ReplyKeyboardRemove(),parse_mode=types.ParseMode.MARKDOWN)
    else:
        """ CURRENT MONTH DATA """
        sql_cur_month_elec = "SELECT ELECTRICITY FROM '%s' WHERE MONTH = '%s' AND YEAR = '%s';" %(kom_tab, datetime.date.today().strftime("%m"), datetime.date.today().strftime("%Y"))
        crsr.execute(sql_cur_month_elec)
        result_cur_elec = crsr.fetchone()[0] # ELEC for current month
        sql_cur_month_hot = "SELECT HOT FROM '%s' WHERE MONTH = '%s' AND YEAR = '%s';" %(kom_tab, datetime.date.today().strftime("%m"), datetime.date.today().strftime("%Y"))
        crsr.execute(sql_cur_month_hot)
        result_cur_hot = crsr.fetchone()[0] # HOT for current month
        sql_cur_month_cold = "SELECT COLD FROM '%s' WHERE MONTH = '%s' AND YEAR = '%s';" %(kom_tab, datetime.date.today().strftime("%m"), datetime.date.today().strftime("%Y"))
        crsr.execute(sql_cur_month_cold)
        result_cur_cold = crsr.fetchone()[0] # COLD for current month
        """ PREVIOUS MONTH DATA """
        def prev_date(n):
            lastMonth = datetime.date.today().replace(day=1) - datetime.timedelta(days=1)
            return lastMonth.strftime(n)
        sql_prev_month = "SELECT * FROM '%s' WHERE MONTH = '%s' AND YEAR = '%s';" %(kom_tab, prev_date("%m"), prev_date("%Y"))
        crsr.execute(sql_prev_month)
        if not crsr.fetchone(): # No data for previous month
            msg_text = text(bold(datetime.date.today().strftime("%B %Y:")),
                                emojize(':high_voltage: ') + code(result_cur_elec),
                                bold("Израсходовано: ") + code("неизвестно"),
                                emojize(':thermometer: ') + code(result_cur_hot),
                                bold("Израсходовано: ") + code("неизвестно"),
                                emojize(':ice: ') + code(result_cur_cold),
                                bold("Израсходовано: ") + code("неизвестно"), sep='\n')
        else:
            sql_prev_list = "SELECT ELECTRICITY, HOT, COLD FROM '%s' WHERE MONTH = '%s' AND YEAR = '%s';" %(kom_tab, prev_date("%m"), prev_date("%Y"))
            crsr.execute(sql_prev_list)
            result_prev_elec = crsr.fetchone()[0] # ELEC for previous month
            crsr.execute(sql_prev_list)
            result_prev_hot = crsr.fetchone()[1] # HOT for previous month
            crsr.execute(sql_prev_list)
            result_prev_cold = crsr.fetchone()[2] # COLD for previous month
            msg_text = text(bold(datetime.date.today().strftime("%B %Y:")),
                                emojize(':high_voltage: ') + code(result_cur_elec),
                                bold("Израсходовано: ") + code(str(int(result_cur_elec) - int(result_prev_elec)) + " кВт/ч"),
                                emojize(':thermometer: ') + code(result_cur_hot),
                                bold("Израсходовано: ") + code(str(int(result_cur_hot) - int(result_prev_hot)) + " м³"),
                                emojize(':ice: ') + code(result_cur_cold),
                                bold("Израсходовано: ") + code(str(int(result_cur_cold) - int(result_prev_cold)) + " м³"), sep='\n')
        await message.answer(msg_text,parse_mode=types.ParseMode.MARKDOWN)
    connection.close()

""" Starting button 3 """
@dp.message_handler(Text(equals=emojize(':gear:')+' Настройки'))
async def process_options(message: types.Message):
    options_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    options_but1 = emojize(':cross_mark:')+' Удалить данные за ' + datetime.date.today().strftime("%B %Y").lower()
    options_but2 = emojize(':skull_and_crossbones:')+' Удалить все данные'
    options_but3 = 'Назад'
    options_kb.add(options_but1).add(options_but2).add(options_but3)
    await message.answer('Настройки',reply_markup=options_kb)


if __name__ == '__main__':
    executor.start_polling(dp)