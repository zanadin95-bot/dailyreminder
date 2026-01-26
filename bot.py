import os
import json
from datetime import datetime, timedelta
import pytz
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
import asyncio
from aiohttp import web

# Singapore timezone
SGT = pytz.timezone('Asia/Singapore')

# Store reminders in a JSON file
REMINDERS_FILE = 'reminders.json'

# Conversation states
TASK, FREQUENCY, TIME, START_DATE, END_DATE, ONE_OFF_DATETIME = range(6)
REMOVE_NUMBER = 0

def load_reminders():
    """Load reminders from JSON file"""
    if os.path.exists(REMINDERS_FILE):
        with open(REMINDERS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_reminders(reminders):
    """Save reminders to JSON file"""
    with open(REMINDERS_FILE, 'w') as f:
        json.dump(reminders, f, indent=2)

# Global reminders storage
reminders = load_reminders()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with main menu"""
    keyboard = [
        ['1. Add Reminder'],
        ['2. See List'],
        ['3. Remove Reminder']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        "Hello Princess Erin <3 I hope this helps you make your life easier and remind of you the important things you need to do. Ready to nudge when you need a little reminder or a little smile! :)\n\n"
        "Choose an option below:",
        reply_markup=reply_markup
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu selections"""
    text = update.message.text
    
    # Show welcome menu if user just sent any text and hasn't seen menu yet
    if not context.user_data.get('menu_shown'):
        context.user_data['menu_shown'] = True
        await start(update, context)
        return
    
    if '1' in text or 'Add' in text:
        return await add_reminder_start(update, context)
    elif '2' in text or 'See' in text or 'List' in text:
        return await see_list(update, context)
    elif '3' in text or 'Remove' in text:
        return await remove_reminder_start(update, context)
    else:
        await update.message.reply_text("Please choose one of the options from the menu.")

# ADD REMINDER FLOW
async def add_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a reminder - ask for task"""
    await update.message.reply_text(
        "📝 What would you like to be reminded about?",
        reply_markup=ReplyKeyboardRemove()
    )
    return TASK

async def get_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save task and ask for frequency"""
    context.user_data['task'] = update.message.text
    
    keyboard = [
        ['Daily'],
        ['Weekly'],
        ['Monthly'],
        ['One-off']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "📅 How often should I remind you?",
        reply_markup=reply_markup
    )
    return FREQUENCY

async def get_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save frequency and ask for appropriate next step"""
    frequency = update.message.text.strip()
    
    if frequency not in ['Daily', 'Weekly', 'Monthly', 'One-off']:
        keyboard = [
            ['Daily'],
            ['Weekly'],
            ['Monthly'],
            ['One-off']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text("Please choose: Daily, Weekly, Monthly, or One-off", reply_markup=reply_markup)
        return FREQUENCY
    
    context.user_data['frequency'] = frequency
    
    if frequency == 'One-off':
        # For one-off, ask for date and time together
        await update.message.reply_text(
            "📅 When should I send this reminder?\n\n"
            "Please enter date and time:\n"
            "Format: YYYY-MM-DD HH:MM\n"
            "Example: 2026-02-15 14:30",
            reply_markup=ReplyKeyboardRemove()
        )
        return ONE_OFF_DATETIME
    else:
        # For recurring, ask for time first
        await update.message.reply_text(
            "⏰ What time should I send the reminder?\n\n"
            "Please enter in 24-hour format (HH:MM)\n"
            "Example: 09:00 or 14:30",
            reply_markup=ReplyKeyboardRemove()
        )
        return TIME

async def get_one_off_datetime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get date and time for one-off reminder"""
    datetime_str = update.message.text.strip()
    
    try:
        # Validate datetime format
        reminder_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        
        # Check if date is in the future (Singapore time)
        now_sgt = datetime.now(SGT).replace(tzinfo=None)
        if reminder_datetime <= now_sgt:
            await update.message.reply_text(
                "❌ Please enter a future date and time!\n\n"
                "Format: YYYY-MM-DD HH:MM\n"
                "Example: 2026-02-15 14:30"
            )
            return ONE_OFF_DATETIME
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid format.\n\n"
            "Please use: YYYY-MM-DD HH:MM\n"
            "Example: 2026-02-15 14:30"
        )
        return ONE_OFF_DATETIME
    
    # Save the one-off reminder
    user_id = str(update.effective_user.id)
    
    if user_id not in reminders:
        reminders[user_id] = []
    
    new_reminder = {
        'task': context.user_data['task'],
        'frequency': 'One-off',
        'datetime': datetime_str,
        'sent': False
    }
    
    reminders[user_id].append(new_reminder)
    save_reminders(reminders)
    
    # Show confirmation
    keyboard = [
        ['1. Add Reminder'],
        ['2. See List'],
        ['3. Remove Reminder']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"✅ Reminder added!\n\n"
        f"📝 Task: {new_reminder['task']}\n"
        f"📅 One-time reminder\n"
        f"🗓️ Date & Time: {datetime_str} SGT\n\n"
        f"Choose your next action:",
        reply_markup=reply_markup
    )
    
    context.user_data.clear()
    return ConversationHandler.END

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save time and ask for start date"""
    time_str = update.message.text.strip()
    
    try:
        # Validate time format
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid time format.\n\n"
            "Please use HH:MM (e.g., 09:00 or 14:30)"
        )
        return TIME
    
    context.user_data['time'] = time_str
    
    keyboard = [
        ['Today'],
        ['Tomorrow'],
        ['Custom Date']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "📅 When should this reminder start?",
        reply_markup=reply_markup
    )
    return START_DATE

async def get_start_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save start date and ask for end date"""
    date_str = update.message.text.strip()
    
    if date_str == 'Today':
        date_str = datetime.now(SGT).strftime("%Y-%m-%d")
    elif date_str == 'Tomorrow':
        tomorrow = datetime.now(SGT) + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
    elif date_str == 'Custom Date':
        await update.message.reply_text(
            "Please enter the start date:\n"
            "Format: YYYY-MM-DD\n"
            "Example: 2026-01-27",
            reply_markup=ReplyKeyboardRemove()
        )
        return START_DATE
    else:
        # Custom date entered
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid date format.\n\n"
                "Please use: YYYY-MM-DD\n"
                "Example: 2026-01-27"
            )
            return START_DATE
    
    context.user_data['start_date'] = date_str
    
    keyboard = [
        ['Never'],
        ['1 Week'],
        ['1 Month'],
        ['3 Months'],
        ['6 Months'],
        ['1 Year'],
        ['Custom Date']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "📅 When should this reminder end?",
        reply_markup=reply_markup
    )
    return END_DATE

async def get_end_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save end date and complete the reminder"""
    date_str = update.message.text.strip()
    
    if date_str == 'Never':
        date_str = None
    elif date_str == 'Custom Date':
        await update.message.reply_text(
            "Please enter the end date:\n"
            "Format: YYYY-MM-DD\n"
            "Example: 2026-12-31",
            reply_markup=ReplyKeyboardRemove()
        )
        return END_DATE
    elif date_str in ['1 Week', '1 Month', '3 Months', '6 Months', '1 Year']:
        start_date = datetime.strptime(context.user_data['start_date'], "%Y-%m-%d")
        
        if date_str == '1 Week':
            end_date = start_date + timedelta(weeks=1)
        elif date_str == '1 Month':
            end_date = start_date + timedelta(days=30)
        elif date_str == '3 Months':
            end_date = start_date + timedelta(days=90)
        elif date_str == '6 Months':
            end_date = start_date + timedelta(days=180)
        elif date_str == '1 Year':
            end_date = start_date + timedelta(days=365)
        
        date_str = end_date.strftime("%Y-%m-%d")
    else:
        try:
            # Validate date format
            end_date = datetime.strptime(date_str, "%Y-%m-%d")
            start_date = datetime.strptime(context.user_data['start_date'], "%Y-%m-%d")
            
            if end_date <= start_date:
                await update.message.reply_text(
                    "❌ End date must be after start date!\n\n"
                    "Please choose again or enter a valid date"
                )
                return END_DATE
                
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid date format.\n\n"
                "Please use: YYYY-MM-DD\n"
                "Example: 2026-12-31"
            )
            return END_DATE
    
    # Save the reminder
    user_id = str(update.effective_user.id)
    
    if user_id not in reminders:
        reminders[user_id] = []
    
    new_reminder = {
        'task': context.user_data['task'],
        'frequency': context.user_data['frequency'],
        'time': context.user_data['time'],
        'start_date': context.user_data['start_date'],
        'end_date': date_str
    }
    
    reminders[user_id].append(new_reminder)
    save_reminders(reminders)
    
    # Show confirmation
    keyboard = [
        ['1. Add Reminder'],
        ['2. See List'],
        ['3. Remove Reminder']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    end_text = f"🗓️ End: {date_str}" if date_str else "🗓️ End: Never"
    
    await update.message.reply_text(
        f"✅ Reminder added!\n\n"
        f"📝 Task: {new_reminder['task']}\n"
        f"📅 Frequency: {new_reminder['frequency']}\n"
        f"⏰ Time: {new_reminder['time']} SGT\n"
        f"🗓️ Start: {new_reminder['start_date']}\n"
        f"{end_text}\n\n"
        f"Choose your next action:",
        reply_markup=reply_markup
    )
    
    context.user_data.clear()
    return ConversationHandler.END

# SEE LIST
async def see_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all reminders"""
    user_id = str(update.effective_user.id)
    
    keyboard = [
        ['1. Add Reminder'],
        ['2. See List'],
        ['3. Remove Reminder']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text(
            "You don't have any reminders yet!\n\n"
            "Use '1. Add Reminder' to create one.",
            reply_markup=reply_markup
        )
        return
    
    message = "📋 Your Reminders:\n\n"
    for i, reminder in enumerate(reminders[user_id], 1):
        message += f"{i}. {reminder['task']}\n"
        message += f"   📅 {reminder['frequency']}\n"
        
        if reminder['frequency'] == 'One-off':
            message += f"   🗓️ {reminder['datetime']} SGT\n"
        else:
            message += f"   ⏰ {reminder['time']} SGT\n"
            message += f"   🗓️ Start: {reminder['start_date']}\n"
            end_text = reminder['end_date'] if reminder['end_date'] else 'Never'
            message += f"   🗓️ End: {end_text}\n"
        
        message += "\n"
    
    await update.message.reply_text(message, reply_markup=reply_markup)

# REMOVE REMINDER FLOW
async def remove_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start removing a reminder"""
    user_id = str(update.effective_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        keyboard = [
            ['1. Add Reminder'],
            ['2. See List'],
            ['3. Remove Reminder']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "You don't have any reminders to remove!",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    
    # Show list with numbers
    message = "📋 Your Reminders:\n\n"
    for i, reminder in enumerate(reminders[user_id], 1):
        if reminder['frequency'] == 'One-off':
            message += f"{i}. {reminder['task']} (One-off, {reminder['datetime']})\n"
        else:
            message += f"{i}. {reminder['task']} ({reminder['frequency']}, {reminder['time']})\n"
    
    message += "\n🗑️ Which reminder would you like to remove?\n"
    message += "Enter the number:"
    
    await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
    return REMOVE_NUMBER

async def remove_reminder_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove the selected reminder"""
    user_id = str(update.effective_user.id)
    
    try:
        number = int(update.message.text.strip())
        
        if 1 <= number <= len(reminders[user_id]):
            removed = reminders[user_id].pop(number - 1)
            save_reminders(reminders)
            
            keyboard = [
                ['1. Add Reminder'],
                ['2. See List'],
                ['3. Remove Reminder']
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"✅ Reminder removed!\n\n"
                f"📝 {removed['task']}\n\n"
                f"Choose your next action:",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                f"❌ Invalid number. Please enter a number between 1 and {len(reminders[user_id])}"
            )
            return REMOVE_NUMBER
            
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number")
        return REMOVE_NUMBER
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current operation"""
    keyboard = [
        ['1. Add Reminder'],
        ['2. See List'],
        ['3. Remove Reminder']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Operation cancelled. Choose an option:",
        reply_markup=reply_markup
    )
    context.user_data.clear()
    return ConversationHandler.END

async def send_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Check and send reminders"""
    # Get current Singapore time
    now_sgt = datetime.now(SGT)
    current_time = now_sgt.strftime("%H:%M")
    current_date = now_sgt.strftime("%Y-%m-%d")
    current_day = now_sgt.day
    current_weekday = now_sgt.weekday()
    
    print(f"Checking reminders at {current_date} {current_time} SGT")
    
    for user_id, user_reminders in reminders.items():
        for reminder in user_reminders:
            should_send = False
            
            # Handle one-off reminders
            if reminder['frequency'] == 'One-off':
                if not reminder.get('sent', False):
                    reminder_dt = datetime.strptime(reminder['datetime'], "%Y-%m-%d %H:%M")
                    reminder_time = reminder_dt.strftime("%H:%M")
                    reminder_date = reminder_dt.strftime("%Y-%m-%d")
                    
                    print(f"One-off check: {reminder_date} {reminder_time} vs {current_date} {current_time}")
                    
                    if current_date == reminder_date and current_time == reminder_time:
                        should_send = True
                        reminder['sent'] = True
                        save_reminders(reminders)
            
            # Handle recurring reminders
            else:
                # Check if within date range
                if current_date < reminder['start_date']:
                    print(f"Reminder not started yet: {reminder['start_date']}")
                    continue
                if reminder['end_date'] and current_date > reminder['end_date']:
                    print(f"Reminder ended: {reminder['end_date']}")
                    continue
                
                # Check if it's time to send
                if reminder['time'] == current_time:
                    print(f"Time matches! Checking frequency: {reminder['frequency']}")
                    if reminder['frequency'] == 'Daily':
                        should_send = True
                    elif reminder['frequency'] == 'Weekly' and current_weekday == 0:
                        should_send = True
                    elif reminder['frequency'] == 'Monthly' and current_day == 1:
                        should_send = True
            
            if should_send:
                print(f"Sending reminder to {user_id}: {reminder['task']}")
                message = "Attention Warrior Erin! Remember to take a break a little, smile and think of the positive things~ Here are the side quests that you need to complete before you get back on with your day, my love :)\n\n"
                message += f"⚔️ {reminder['task']}"
                try:
                    await context.bot.send_message(chat_id=int(user_id), text=message)
                    print(f"✅ Reminder sent successfully!")
                except Exception as e:
                    print(f"❌ Error sending to {user_id}: {e}")

def main():
    """Start the bot"""
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        print("⚠️  Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Add reminder conversation handler
    add_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(1|Add)'), add_reminder_start)
        ],
        states={
            TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_task)],
            FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_frequency)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            START_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_start_date)],
            END_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_end_date)],
            ONE_OFF_DATETIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_one_off_datetime)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Remove reminder conversation handler
    remove_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex('^(3|Remove)'), remove_reminder_start)
        ],
        states={
            REMOVE_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, remove_reminder_confirm)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(add_conv_handler)
    app.add_handler(remove_conv_handler)
    app.add_handler(MessageHandler(filters.Regex('^(2|See|List)'), see_list))
    
    # Catch-all handler for menu and first message - must be last
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
    
    # Set up job queue for reminders
    job_queue = app.job_queue
    job_queue.run_repeating(send_reminders, interval=60, first=10)
    
    print("🤖 Bot is running!")
    
    # Start health check web server for Render
    async def health_check(request):
        return web.Response(text="Bot is running!")
    
    async def start_web_server():
        web_app = web.Application()
        web_app.router.add_get('/', health_check)
        web_app.router.add_get('/health', health_check)
        runner = web.AppRunner(web_app)
        await runner.setup()
        port = int(os.getenv('PORT', 10000))
        site = web.TCPSite(runner, '0.0.0.0', port)
        await site.start()
        print(f"🌐 Web server running on port {port}")
    
    # Start web server
    asyncio.get_event_loop().create_task(start_web_server())
    
    # Run the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
