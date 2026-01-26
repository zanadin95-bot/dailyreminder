import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

# Store reminders in a JSON file
REMINDERS_FILE = 'reminders.json'

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

# Global reminders storage: {user_id: {time: "HH:MM", tasks: ["task1", "task2"]}}
reminders = load_reminders()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    await update.message.reply_text(
        "👋 Hey! I'm your Daily Reminder Bot!\n\n"
        "Commands:\n"
        "/settime HH:MM - Set your daily reminder time (24-hour format)\n"
        "/addtask Your task here - Add a task to your daily reminders\n"
        "/removetask Task number - Remove a task\n"
        "/list - See all your tasks\n"
        "/mystatus - Check your reminder settings\n"
        "/help - Show this message again"
    )

async def set_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set the daily reminder time"""
    user_id = str(update.effective_user.id)
    
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /settime HH:MM (e.g., /settime 09:00)")
        return
    
    time_str = context.args[0]
    try:
        # Validate time format
        datetime.strptime(time_str, "%H:%M")
        
        if user_id not in reminders:
            reminders[user_id] = {"time": time_str, "tasks": []}
        else:
            reminders[user_id]["time"] = time_str
        
        save_reminders(reminders)
        await update.message.reply_text(f"✅ Daily reminder time set to {time_str} UTC!")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid time format. Use HH:MM (e.g., 09:00)")

async def add_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a task to daily reminders"""
    user_id = str(update.effective_user.id)
    
    if not context.args:
        await update.message.reply_text("Usage: /addtask Your task description here")
        return
    
    task = " ".join(context.args)
    
    if user_id not in reminders:
        reminders[user_id] = {"time": "09:00", "tasks": []}
    
    reminders[user_id]["tasks"].append(task)
    save_reminders(reminders)
    
    await update.message.reply_text(f"✅ Task added: {task}\n\nYou now have {len(reminders[user_id]['tasks'])} task(s).")

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a task by number"""
    user_id = str(update.effective_user.id)
    
    if user_id not in reminders or not reminders[user_id]["tasks"]:
        await update.message.reply_text("You don't have any tasks to remove!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /removetask <task_number>\n\nUse /list to see task numbers.")
        return
    
    try:
        task_num = int(context.args[0]) - 1
        if 0 <= task_num < len(reminders[user_id]["tasks"]):
            removed_task = reminders[user_id]["tasks"].pop(task_num)
            save_reminders(reminders)
            await update.message.reply_text(f"✅ Removed: {removed_task}")
        else:
            await update.message.reply_text("❌ Invalid task number!")
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid task number!")

async def list_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all tasks"""
    user_id = str(update.effective_user.id)
    
    if user_id not in reminders or not reminders[user_id]["tasks"]:
        await update.message.reply_text("You don't have any tasks yet!\n\nUse /addtask to add one.")
        return
    
    tasks = reminders[user_id]["tasks"]
    message = "📋 Your Daily Tasks:\n\n"
    for i, task in enumerate(tasks, 1):
        message += f"{i}. {task}\n"
    
    await update.message.reply_text(message)

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's reminder settings"""
    user_id = str(update.effective_user.id)
    
    if user_id not in reminders:
        await update.message.reply_text("You haven't set up any reminders yet!\n\nUse /settime and /addtask to get started.")
        return
    
    user_data = reminders[user_id]
    message = f"⚙️ Your Settings:\n\n"
    message += f"⏰ Reminder Time: {user_data.get('time', 'Not set')} UTC\n"
    message += f"📝 Tasks: {len(user_data.get('tasks', []))}"
    
    await update.message.reply_text(message)

async def send_daily_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Send daily reminders to all users"""
    current_time = datetime.utcnow().strftime("%H:%M")
    
    for user_id, data in reminders.items():
        if data.get("time") == current_time and data.get("tasks"):
            message = "🔔 Daily Reminder!\n\n"
            message += "📋 Your tasks for today:\n\n"
            for i, task in enumerate(data["tasks"], 1):
                message += f"{i}. {task}\n"
            
            try:
                await context.bot.send_message(chat_id=int(user_id), text=message)
            except Exception as e:
                print(f"Error sending to {user_id}: {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help message"""
    await start(update, context)

def main():
    """Start the bot"""
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    
    if not TOKEN:
        print("⚠️  Error: TELEGRAM_BOT_TOKEN environment variable not set!")
        return
    
    # Create application
    app = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("settime", set_time))
    app.add_handler(CommandHandler("addtask", add_task))
    app.add_handler(CommandHandler("removetask", remove_task))
    app.add_handler(CommandHandler("list", list_tasks))
    app.add_handler(CommandHandler("mystatus", my_status))
    app.add_handler(CommandHandler("help", help_command))
    
    # Set up job queue to check for reminders every minute
    job_queue = app.job_queue
    job_queue.run_repeating(send_daily_reminder, interval=60, first=10)
    
    print("🤖 Bot is running!")
    
    # Run the bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()