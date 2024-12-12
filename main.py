import asyncio
import logging
import os
import uuid
from concurrent.futures import ProcessPoolExecutor

from aiogram import Bot, Dispatcher, types, Router, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, FSInputFile, CallbackQuery
import config as cnfg

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from FaceSimilars import find_most_similar_face
from multiprocessing import Queue

from ObjectStorage import ObjectStorage

logging.basicConfig(level=logging.INFO)
bot = Bot(token=cnfg.TG_BOT_API)
dp = Dispatcher()


scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

class ActorSearchStates(StatesGroup):
    CHOOSING_TYPE = State()  # Выбор актёра или актрисы
    PHOTO_UPLOAD = State()   # Загрузка фотографии

actor_router = Router()
text_button = "Узнать схожесть на актёра/актрису по фото"


GLOBAL_QUEUE = asyncio.Queue()

result_queue = Queue()

executor = ProcessPoolExecutor()


async def processing_answer():
    while True:
        data, chat_id = await GLOBAL_QUEUE.get()

        most_similar_photo = await asyncio.get_running_loop().run_in_executor(
            executor, find_most_similar_face, data["CHOOSING_TYPE"], data["PHOTO_UPLOAD"]
        )

        await answer_to_user(data, most_similar_photo, chat_id)

        GLOBAL_QUEUE.task_done()



async def answer_to_user(data, most_similar_photo, chat_id):
    btn = InlineKeyboardButton(text=text_button, callback_data="start")
    row = [btn]
    rows = [row]
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    if most_similar_photo!=None:
        await bot.send_photo(
            chat_id=chat_id, caption=f"Человек на фото похож на {most_similar_photo[1]}",
            photo=FSInputFile(path=most_similar_photo[0]), reply_markup=markup,
        )
        os.remove(most_similar_photo[0])
    else:
        await bot.send_message(chat_id=chat_id, text="На вашем фото лицо не обнаружено(", reply_markup=markup)
    os.remove(data["PHOTO_UPLOAD"])




@actor_router.message(Command("start"))
async def start_find(message: types.Message, state: FSMContext)->None:
    await state.set_state(ActorSearchStates.CHOOSING_TYPE)
    btn1 = InlineKeyboardButton(text="Актёр", callback_data="actors")
    btn2 = InlineKeyboardButton(text="Актриса", callback_data="actresses")
    row = [btn1, btn2]
    rows = [row]
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(
        "Узнайте на кого похож человек! Выберите, кого искать. Актёра или актрису?",
        reply_markup=markup,
    )

@actor_router.callback_query(F.data == "start")
async def process_callback_start(callback_query: types.CallbackQuery, state: FSMContext):
    await start_find(callback_query.message, state)
    await callback_query.answer()


@actor_router.callback_query(ActorSearchStates.CHOOSING_TYPE)
async def upload_photo(callback_query: CallbackQuery, state: FSMContext)->None:
    category = None
    if callback_query.data in cnfg.Categories:
        category = callback_query.data
    else:
        btn1 = InlineKeyboardButton(text="Актёр", callback_data="actors")
        btn2 = InlineKeyboardButton(text="Актриса", callback_data="actresses")
        row = [btn1, btn2]
        rows = [row]
        markup = InlineKeyboardMarkup(inline_keyboard=rows)
        await callback_query.message.answer("Ошибка! Повторите выбор.", reply_markup=markup,)
    if category is not None:
        await state.update_data(CHOOSING_TYPE=category)
        await state.set_state(ActorSearchStates.PHOTO_UPLOAD)
        await callback_query.message.answer(
            "Загрузите фото человека", reply_markup=ReplyKeyboardRemove()
        )


@actor_router.message(ActorSearchStates.PHOTO_UPLOAD, F.photo)
async def finish(message: types.Message, state: FSMContext) -> None:
    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    unique_filename = str(uuid.uuid4()) + ".jpg"
    user_photos_dir = "user_photos"
    if not os.path.exists(user_photos_dir):
        os.makedirs(user_photos_dir)
    unique_filepath = os.path.join(user_photos_dir, unique_filename)
    downloaded_file = await bot.download_file(file.file_path)
    with open(unique_filepath, "wb") as photo:
        photo.write(downloaded_file.read())
    data = await state.update_data(PHOTO_UPLOAD=unique_filepath)
    await message.answer("Ожидайте результата, это займёт несколько минут")
    await state.clear()
    await GLOBAL_QUEUE.put([data, message.chat.id])
    await processing_answer()


async def main():
    object_storage = ObjectStorage()
    object_storage.get_sqlite_file()
    dp.include_router(actor_router)
    asyncio.create_task(processing_answer())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
