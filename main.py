import os
import threading
import telebot
from flask import Flask

BOT_TOKEN = os.getenv("BOT_TOKEN")
print(f"BOT_TOKEN found: {BOT_TOKEN is not None}")

app = Flask(__name__)

if BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN)

    @bot.message_handler(commands=['start'])
    def start(m):
        bot.reply_to(m, "🔥 MD Hasan v17 SECURE 24/7 READY! Bot is LIVE! Send /signal for trade!")

    @bot.message_handler(commands=['signal'])
    def signal(m):
        bot.reply_to(m, "📈 SIGNAL: EUR/USD UP ⬆️ Time: 1 MIN")

    def run_bot():
        print("Bot polling started...")
        bot.infinity_polling()

    threading.Thread(target=run_bot, daemon=True).start()
else:
    print("ERROR: BOT_TOKEN not found in Environment!")

@app.route('/')
def home():
    return "Bot is Running!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)