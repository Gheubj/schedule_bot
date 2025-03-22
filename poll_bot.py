from dotenv import load_dotenv
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from stations import OPTIONS, BUTTON_NAMES
import random

load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT')
ADMIN_ID = int(os.getenv('ADMIN_ID'))

# Sticker IDs
STICKERS = {
    'welcome': "CAACAgIAAxkBAAENOsRnRxxxz0py523T_b1eXia6n8DeRgACig4AAtEh8EkHpmbhWHEjLjYE",
    'admin_only': "CAACAgIAAxkBAAENOsZnRxycMewnQH4n9UGIVLB84OHchgACTg8AAv7T8Un3r_YZptnhwTYE",
    'not_started': "CAACAgIAAxkBAAENOshnRxzOaH8MLgw6V4kuD7_ph2ueIgACQgsAAr8d8En10koHIoNIwDYE",
    'voted': "CAACAgIAAxkBAAENOspnRxzZ-Sf5P7VOJqm7FVc2szUs1wACiAsAAoCB8EmzCVuNQkIAAUk2BA",
    'answer': "CAACAgIAAxkBAAENOtdnRyCauFrBLJ8rnO6v3tUJfz6J_AACYQ0AAhyC6EmrSbjm6IWGCDYE",
}

# Global poll state
active_poll = {
    'is_active': False,
    'votes': {},
    'creator_id': None,
    'participants': set(),  # Хранение ID всех участников
    'pending_votes': {},  # Хранение временных голосов для подтверждения
    'admin_message_id': None,  # ID сообщения с результатами у админа
    'impressions': {  # Хранение впечатлений пользователей
        'like': 0,
        'neutral': 0,
        'dislike': 0
    }
}

# Список пользователей, ожидающих начала голосования
waiting_users = set()

# Кнопки для впечатлений
IMPRESSIONS_BUTTONS = [
    InlineKeyboardButton("понравилось", callback_data="impression_like"),
    InlineKeyboardButton("не знаю", callback_data="impression_neutral"),
    InlineKeyboardButton("не понравилось", callback_data="impression_dislike")
]

async def create_poll_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(BUTTON_NAMES["1"], callback_data="vote_1"),
            InlineKeyboardButton(BUTTON_NAMES["7"], callback_data="vote_7")
        ],
 
        [
            InlineKeyboardButton(BUTTON_NAMES["2"], callback_data="vote_2"),
            InlineKeyboardButton(BUTTON_NAMES["8"], callback_data="vote_8")
        ],

        [
            InlineKeyboardButton(BUTTON_NAMES["3"], callback_data="vote_3"),
            InlineKeyboardButton(BUTTON_NAMES["9"], callback_data="vote_9")
        ],
       
        [
            InlineKeyboardButton(BUTTON_NAMES["4"], callback_data="vote_4"),
            InlineKeyboardButton(BUTTON_NAMES["10"], callback_data="vote_10")
        ],
     
        [
            InlineKeyboardButton(BUTTON_NAMES["5"], callback_data="vote_5"),
            InlineKeyboardButton(BUTTON_NAMES["11"], callback_data="vote_11")
        ],

        [
            InlineKeyboardButton(BUTTON_NAMES["6"], callback_data="vote_6"),
            InlineKeyboardButton(BUTTON_NAMES["12"], callback_data="vote_12")
        ]
    ]
    return keyboard

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not active_poll['is_active']:
        await update.message.reply_sticker(STICKERS['not_started'])
        await update.message.reply_text(
            "Голосование еще не началось, подождите, пожалуйста!\n"
        )
    else:
        # Отправляем приветственный стикер, если голосование активно
        await update.message.reply_sticker(STICKERS['welcome'])
        keyboard = await create_poll_keyboard()
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📊 Голосование: Какая станция вам понравилась больше всего?\n\n"
            "Нажмите, чтобы узнать полное название станции\n\n"
            "Выберите вариант:\n\n",
            reply_markup=reply_markup
        )

async def start_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверяем, является ли пользователь админом
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_sticker(STICKERS['admin_only'])
        await update.message.reply_text("❌ Только администратор может начинать голосование!")
        return
        
    if active_poll['is_active']:
        await update.message.reply_text("Опрос уже запущен!")
        return
        
    active_poll['is_active'] = True
    active_poll['votes'] = {}
    active_poll['creator_id'] = update.message.from_user.id
    active_poll['participants'].clear()
    active_poll['pending_votes'].clear()
    active_poll['admin_message_id'] = None  # Сбрасываем ID сообщения админа
    active_poll['impressions'] = {'like': 0, 'neutral': 0, 'dislike': 0}  # Сбрасываем впечатления
    
    keyboard = await create_poll_keyboard()
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📊 Голосование: Какая станция вам понравилась больше всего?\n\n"
        "Нажмите, чтобы узнать полное название станции\n\n"
        "Выберите вариант:",
        reply_markup=reply_markup
    )
    
    # Уведомляем пользователей, ожидавших начала голосования
    for user_id in waiting_users:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="Голосование началось! Нажмите кнопку ниже, чтобы принять участие.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Принять участие", callback_data="vote_start")]
                ])
            )
        except Exception as e:
            pass  # Убираем логирование ошибок
    
    # Очищаем список ожидающих
    waiting_users.clear()

async def end_poll(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Проверяем, является ли пользователь админом
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_sticker(STICKERS['admin_only'])
        await update.message.reply_text("❌ Только администратор может завершать голосование!")
        return
        
    if not active_poll['is_active']:
        await update.message.reply_text("Нет активного голосования, подождите, пожалуйста!")
        return
        
    results = await show_results()
    active_poll['is_active'] = False
    active_poll['admin_message_id'] = None  # Сбрасываем ID сообщения админа
    
    # Отправляем результаты всем участникам
    for user_id in active_poll['participants']:
        try:
            await context.bot.send_message(chat_id=user_id, text=results)
        except Exception as e:
            pass  # Убираем логирование ошибок
    
    # Отправляем отзывы админу
    impressions_summary = (
        f"📊 Отзывы пользователей:\n\n"
        f"👍 Понравилось: {active_poll['impressions']['like']}\n"
        f"🤔 Не знаю: {active_poll['impressions']['neutral']}\n"
        f"👎 Не понравилось: {active_poll['impressions']['dislike']}"
    )
    await update.message.reply_text(impressions_summary)
    
    await update.message.reply_text(results)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    
    await query.answer()
    
    if query.data.startswith("vote_"):
        if not active_poll['is_active']:
            # Сначала отправляем новый стикер
            await context.bot.send_sticker(
                chat_id=query.message.chat_id,
                sticker=STICKERS['answer']
            )
            # Затем отправляем сообщение
            await query.message.edit_text("Голосование уже завершено!")
            return

        # Проверяем, голосовал ли пользователь ранее
        if user_id in active_poll['participants']:
            await query.message.reply_sticker(STICKERS['admin_only'])
            await query.message.reply_text("Вы уже проголосовали! Спасибо за участие.")
            return
            
        option = query.data.split("_")[1]
        
        # Создаем клавиатуру для подтверждения
        confirm_keyboard = [
            [
                InlineKeyboardButton("Да ✅", callback_data=f"confirm_{option}"),
                InlineKeyboardButton("Нет ❌", callback_data="cancel_vote")
            ]
        ]
        confirm_markup = InlineKeyboardMarkup(confirm_keyboard)
        
        # Сохраняем временный выбор
        active_poll['pending_votes'][user_id] = option
        
        await query.message.edit_text(
            f"📊 Голосование: Какая станция вам понравилась больше всего?\n\n"
            f"Вы выбрали:\n{OPTIONS[option]}\n\n"
            f"Подтвердить выбор?",
            reply_markup=confirm_markup
        )
    
    elif query.data.startswith("confirm_"):
        option = query.data.split("_")[1]
        if user_id in active_poll['pending_votes']:
            # Подтверждаем голос
            active_poll['votes'][option] = active_poll['votes'].get(option, 0) + 1
            active_poll['participants'].add(user_id)
            del active_poll['pending_votes'][user_id]
            
            # Убираем кнопки и вопрос
            await query.message.edit_text(
                f"Ваш голос за {OPTIONS[option]} учтен! Спасибо за участие в голосовании."
            )
            
            # Отправляем стикер в новом сообщении
            await context.bot.send_sticker(
                chat_id=query.message.chat_id,
                sticker=STICKERS['voted']
            )
            
            # Обновляем результаты для админа
            await update_admin_results(context)

            # Отправляем сообщение с вопросом о впечатлениях
            await query.message.reply_text(
                "Какие ваши впечатления от большой перемены?",
                reply_markup=InlineKeyboardMarkup([IMPRESSIONS_BUTTONS])
            )

    elif query.data == "cancel_vote":
        if user_id in active_poll['pending_votes']:
            del active_poll['pending_votes'][user_id]
            
            # Возвращаем исходную клавиатуру для голосования
            keyboard = await create_poll_keyboard()
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                "📊 Голосование: Какая станция вам понравилась больше всего?\n\n"
                "Выберите вариант:",
                reply_markup=reply_markup
            )

    # Обработка кнопок впечатлений
    elif query.data.startswith("impression_"):
        impression = query.data.split("_")[1]
        if impression == "like":
            active_poll['impressions']['like'] += 1
            await query.message.edit_text("Спасибо за ваш отзыв! Мы рады, что вам понравилось.")
        elif impression == "neutral":
            active_poll['impressions']['neutral'] += 1
            await query.message.edit_text("Спасибо за ваш отзыв! Надеемся, что в следующий раз вам понравится больше.")
        elif impression == "dislike":
            active_poll['impressions']['dislike'] += 1
            await query.message.edit_text("Спасибо за ваш отзыв! Нам жаль, что вам не понравилось.")

async def show_results():
    results = []
    total_votes = sum(active_poll['votes'].values())
    
    # Создаем список всех станций с их голосами
    stations_results = []
    for option_id, option_name in BUTTON_NAMES.items():
        votes = active_poll['votes'].get(option_id, 0)
        percentage = (votes / total_votes * 100) if total_votes > 0 else 0
        stations_results.append({
            'id': option_id,
            'name': option_name,
            'votes': votes,
            'percentage': percentage
        })
    
    # Сортируем по количеству голосов (по убыванию)
    stations_results.sort(key=lambda x: (-x['votes'], x['id']))
    
    # Первое место - победитель
    winner = stations_results[0] if stations_results and stations_results[0]['votes'] > 0 else None
    
    header = "📊 Результаты голосования:\n\n"
    if winner:
        header += f"🏆 Победитель: {winner['name']}\n\n"
    
    # Формируем отсортированный список результатов
    for i, station in enumerate(stations_results, 1):
        # Добавляем корону для победителя
        prefix = "👑 " if winner and station['id'] == winner['id'] else "   "
        # Добавляем номер места
        place = f"{i}. "
        results.append(f"{prefix}{place}{station['name']}: {station['votes']} голосов ({station['percentage']:.1f}%)")
    
    return header + "\n".join(results)

async def update_admin_results(context: ContextTypes.DEFAULT_TYPE):
    if not active_poll['is_active']:
        return
        
    results = await show_results()
    
    try:
        if active_poll['admin_message_id'] is None:
            # Первый раз отправляем сообщение
            message = await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"{results}\n\nОбновлено автоматически при голосовании"
            )
            active_poll['admin_message_id'] = message.message_id
        else:
            # Обновляем существующее сообщение
            await context.bot.edit_message_text(
                chat_id=ADMIN_ID,
                message_id=active_poll['admin_message_id'],
                text=f"{results}\n\nОбновлено автоматически при голосовании"
            )
    except Exception as e:
        pass  # Убираем логирование ошибок

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("startpoll", start_poll))
    application.add_handler(CommandHandler("endpoll", end_poll))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda update, context: update.message.reply_text("Команда не найдена")))

    application.run_polling(poll_interval=1.0)

if __name__ == '__main__':
    main()