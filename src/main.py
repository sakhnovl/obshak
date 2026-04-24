import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from typing import DefaultDict
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, BaseFilter
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv

from database.db import db
from src.ai import get_ai_agent

load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN')
ADMIN_IDS = [int(id_.strip()) for id_ in os.getenv('TELEGRAM_ADMIN_IDS', '').split(',') if id_.strip()]

# Initialize AI agent
ai_agent = get_ai_agent()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 5
USER_REQUEST_LOG: DefaultDict[int, deque[float]] = defaultdict(deque)

# Bot and Dispatcher
dp = Dispatcher(storage=MemoryStorage())


def get_editable_message(callback: CallbackQuery) -> Message | None:
    callback_message = callback.message
    if isinstance(callback_message, Message):
        return callback_message
    return None

class AdminFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        user = message.from_user
        return bool(user and user.id in ADMIN_IDS)

class AdminStates(StatesGroup):
    waiting_for_key = State()
    waiting_for_model = State()
    waiting_for_model_priority = State()
    waiting_for_key_id = State()
    waiting_for_model_id = State()
    waiting_for_user_id = State()


def is_rate_limited(request_times, current_time):
    window_start = current_time - RATE_LIMIT_WINDOW_SECONDS
    while request_times and request_times[0] <= window_start:
        request_times.popleft()

    if len(request_times) >= RATE_LIMIT_MAX_REQUESTS:
        return True

    request_times.append(current_time)
    return False

async def get_admin_menu():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ”‘ Keys", callback_data="admin_keys"),
         InlineKeyboardButton(text="рџ¤– Models", callback_data="admin_models")],
        [InlineKeyboardButton(text="рџ§№ Reset All", callback_data="admin_reset_all")],
        [InlineKeyboardButton(text="вќЊ Close", callback_data="admin_close")]
    ])
    return keyboard

@dp.message(Command("admin"), AdminFilter())
async def cmd_admin_menu(message: Message):
    await message.answer("рџ›  Admin Panel", reply_markup=await get_admin_menu())

@dp.callback_query(F.data == "admin_close")
async def cb_admin_close(callback: CallbackQuery):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    try:
        await callback_message.edit_text("Admin menu closed.")
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "admin_reset_all", AdminFilter())
async def cb_admin_reset_all(callback: CallbackQuery):
    callback_message = get_editable_message(callback)

    try:
        await db.reset_all_contexts()
        await callback.answer("All contexts reset!", show_alert=True)
    except Exception as e:
        logger.error(f"Error resetting all contexts: {e}")
        await callback.answer("Error resetting contexts.", show_alert=True)
    
    if callback_message:
        try:
            await callback_message.edit_reply_markup(reply_markup=await get_admin_menu())
        except TelegramBadRequest:
            pass

@dp.callback_query(F.data == "admin_keys", AdminFilter())
async def cb_admin_keys(callback: CallbackQuery):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ“‹ List Keys", callback_data="keys_list")],
        [InlineKeyboardButton(text="вћ• Add Key", callback_data="keys_add")],
        [InlineKeyboardButton(text="рџ—‘ Delete Key", callback_data="keys_del")],
        [InlineKeyboardButton(text="в¬…пёЏ Back", callback_data="admin_main")]
    ])
    try:
        await callback_message.edit_text("рџ”‘ Key Management", reply_markup=keyboard)
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "admin_models", AdminFilter())
async def cb_admin_models(callback: CallbackQuery):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="рџ“‹ List Models", callback_data="models_list")],
        [InlineKeyboardButton(text="вћ• Add Model", callback_data="models_add")],
        [InlineKeyboardButton(text="рџ—‘ Delete Model", callback_data="models_del")],
        [InlineKeyboardButton(text="в¬…пёЏ Back", callback_data="admin_main")]
    ])
    try:
        await callback_message.edit_text("рџ¤– Model Management", reply_markup=keyboard)
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "admin_main", AdminFilter())
async def cb_admin_main(callback: CallbackQuery):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    try:
        await callback_message.edit_text("рџ›  Admin Panel", reply_markup=await get_admin_menu())
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "keys_list", AdminFilter())
async def cb_keys_list(callback: CallbackQuery):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    try:
        keys = await db.list_gemini_keys()
        if not keys:
            text = "No keys found."
        else:
            text = "Gemini Keys:\n"
            for k in keys:
                masked = k['api_key'][:8] + "..." + k['api_key'][-4:]
                text += f"ID {k['id']}: {masked}\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="в¬…пёЏ Back", callback_data="admin_keys")]
        ])
        try:
            await callback_message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            pass
    except Exception as e:
        logger.error(f"Error listing keys: {e}")
        await callback.answer("Error listing keys.", show_alert=True)

@dp.callback_query(F.data == "models_list", AdminFilter())
async def cb_models_list(callback: CallbackQuery):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    try:
        models = await db.list_gemini_models()
        if not models:
            text = "No models found."
        else:
            text = "Gemini Models:\n"
            for m in models:
                text += f"ID {m['id']}: {m['model_name']} (priority: {m['priority']})\n"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="в¬…пёЏ Back", callback_data="admin_models")]
        ])
        try:
            await callback_message.edit_text(text, reply_markup=keyboard)
        except TelegramBadRequest:
            pass
    except Exception as e:
        logger.error(f"Error listing models: {e}")
        await callback.answer("Error listing models.", show_alert=True)

@dp.callback_query(F.data == "models_add", AdminFilter())
async def cb_models_add(callback: CallbackQuery, state: FSMContext):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    await callback_message.edit_text("Please send the model name:")
    await state.set_state(AdminStates.waiting_for_model)
    await callback.answer()

@dp.callback_query(F.data == "models_del", AdminFilter())
async def cb_models_del(callback: CallbackQuery, state: FSMContext):
    callback_message = get_editable_message(callback)
    if not callback_message:
        return

    await callback_message.edit_text("Please send the Model ID to delete:")
    await state.set_state(AdminStates.waiting_for_model_id)
    await callback.answer()

@dp.message(AdminStates.waiting_for_key, AdminFilter())
async def process_add_key(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("вќЊ Empty key is not allowed.")
        await state.clear()
        return

    try:
        key_id = await db.add_gemini_key(message.text)
        await message.answer(f"вњ… Key added with ID {key_id}")
    except Exception as e:
        logger.error(f"Error adding key: {e}")
        await message.answer("вќЊ Error adding key.")
    await state.clear()

@dp.message(AdminStates.waiting_for_key_id, AdminFilter())
async def process_del_key(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("вќЊ Invalid ID or error deleting key.")
        await state.clear()
        return

    try:
        count = await db.delete_gemini_key(int(message.text))
        await message.answer("вњ… Deleted {} key(s).".format(count))
    except Exception as e:
        logger.error(f"Error deleting key: {e}")
        await message.answer("вќЊ Invalid ID or error deleting key.")
    await state.clear()

@dp.message(AdminStates.waiting_for_model, AdminFilter())
async def process_add_model(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("вќЊ Error adding model. Use: model_name [priority]")
        await state.clear()
        return

    try:
        # we can add priority if they send "name priority"
        parts = message.text.split()
        name = parts[0]
        priority = int(parts[1]) if len(parts) > 1 else 0
        model_id = await db.add_gemini_model(name, priority)
        await message.answer(f"вњ… Model added with ID {model_id}")
    except Exception as e:
        logger.error(f"Error adding model: {e}")
        await message.answer("вќЊ Error adding model. Use: model_name [priority]")
    await state.clear()

@dp.message(AdminStates.waiting_for_model_id, AdminFilter())
async def process_del_model(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("вќЊ Invalid ID or error deleting model.")
        await state.clear()
        return

    try:
        count = await db.delete_gemini_model(int(message.text))
        await message.answer("вњ… Deleted {} model(s).".format(count))
    except Exception as e:
        logger.error(f"Error deleting model: {e}")
        await message.answer("вќЊ Invalid ID or error deleting model.")
    await state.clear()

@dp.message(Command("cancel"), AdminFilter())
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Operation cancelled. State cleared.")

@dp.message(Command("clear_context"), AdminFilter())
async def cmd_clear_context(message: Message):
    command_text = message.text or ""
    args = command_text.split()
    if len(args) < 2:
        await message.answer("Usage: /clear_context <user_id>")
        return
    try:
        user_id = int(args[1])
        count = await db.clear_user_context(user_id)
        if count > 0:
            await message.answer(f"Context for user {user_id} cleared. Removed {count} messages.")
        else:
            await message.answer(f"No context found for user {user_id}.")
    except ValueError:
        await message.answer("Invalid user ID. Please provide a numeric ID.")
    except Exception as e:
        logger.error(f"Error clearing context: {e}")
        await message.answer("An error occurred while clearing the context.")

@dp.message(F.text)
async def handle_message(message: types.Message):
    user = message.from_user
    text = message.text
    if not user or not text:
        return

    logger.info("Handling message from %s: %s...", user.id, text[:20])

    user_id = user.id
    username = user.username
    first_name = user.first_name

    if is_rate_limited(USER_REQUEST_LOG[user_id], time.monotonic()):
        logger.info(f"User {user_id} is rate limited")
        return

    try:
        history = await db.get_user_context(user_id)
        await db.save_message(user_id, username, first_name, 'user', text)
        response_text = await ai_agent.get_response(user_id, text, history)
        await message.reply(response_text)
        await db.save_message(user_id, username, first_name, 'model', response_text)
    except Exception as e:
        logger.error(f"Error handling message from {user_id}: {e}", exc_info=True)
        await message.answer("Sorry, I encountered an error. Please try again later.")

async def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is not configured")

    bot = Bot(token=BOT_TOKEN)

    # Initialize DB connection pool
    await db.connect()
    # Initialize tables
    await db.init_db()
    
    try:
        logger.info("Bot started...")
        await dp.start_polling(bot)
    finally:
        # Close DB connection pool
        await db.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped")

