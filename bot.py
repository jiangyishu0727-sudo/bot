import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# ====== 配置 ======
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8788455726:AAG-h0aeGdrLixZqTQQBPz-qdBF25Yb1bw8")
API_KEY = os.environ.get("API_KEY", "sk-iwUek2ioI5KsquzkqljnrC4ZgTFAwqalPW5UizWr2nCOTvGN")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.68886868.xyz")
MODEL = os.environ.get("MODEL", "claude-opus-4-6")

# ====== 初始化 ======
logging.basicConfig(level=logging.INFO)
client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)

# 每个用户的对话历史
user_histories = {}

# ====== 命令处理 ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "你好！我是顾深 AI 助手 🤖\n\n直接发消息给我就可以聊天。\n发 /clear 可以清除对话记录。"
    )

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_histories[user_id] = []
    await update.message.reply_text("✅ 对话记录已清除，开始新对话吧！")

# ====== 消息处理 ======
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # 初始化该用户的历史
    if user_id not in user_histories:
        user_histories[user_id] = []

    # 添加用户消息
    user_histories[user_id].append({"role": "user", "content": user_text})

    # 限制历史长度，最多保留20条
    if len(user_histories[user_id]) > 20:
        user_histories[user_id] = user_histories[user_id][-20:]

    # 发送"正在输入"状态
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": "你是一个有帮助的AI助手，用中文回复。"}
            ] + user_histories[user_id],
            max_tokens=2000,
        )
        reply = response.choices[0].message.content
        user_histories[user_id].append({"role": "assistant", "content": reply})
        await update.message.reply_text(reply)

    except Exception as e:
        logging.error(f"API error: {e}")
        await update.message.reply_text(f"❌ 出错了：{str(e)}")

# ====== 启动 ======
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot 启动中...")
    app.run_polling()
