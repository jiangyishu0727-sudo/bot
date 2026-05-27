import os
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_KEY = os.environ.get("API_KEY", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.68886868.xyz")
MODEL = os.environ.get("MODEL", "claude-opus-4-6")

logging.basicConfig(level=logging.INFO)
user_histories = {}

# HTTP健康检查
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, *args):
        pass

def run_server():
    port = int(os.environ.get("PORT", 10000))
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()

def call_ai(messages):
    resp = requests.post(
        f"{API_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "max_tokens": 2000},
        timeout=60
    )
    return resp.json()["choices"][0]["message"]["content"]

def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    resp = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", params=params, timeout=35)
    return resp.json()

def send_message(chat_id, text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=10
    )

def send_typing(chat_id):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendChatAction",
        json={"chat_id": chat_id, "action": "typing"},
        timeout=5
    )

def main():
    threading.Thread(target=run_server, daemon=True).start()
    logging.info("Bot 启动中...")
    offset = None
    while True:
        try:
            result = get_updates(offset)
            for update in result.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                if not chat_id or not text:
                    continue
                if text == "/start":
                    send_message(chat_id, "你好！我是顾深 AI 助手 🤖\n直接发消息聊天，/clear 清除记录。")
                    continue
                if text == "/clear":
                    user_histories[chat_id] = []
                    send_message(chat_id, "✅ 对话记录已清除！")
                    continue
                if chat_id not in user_histories:
                    user_histories[chat_id] = []
                user_histories[chat_id].append({"role": "user", "content": text})
                if len(user_histories[chat_id]) > 20:
                    user_histories[chat_id] = user_histories[chat_id][-20:]
                send_typing(chat_id)
                try:
                    reply = call_ai([{"role": "system", "content": "你是一个有帮助的AI助手，用中文回复。"}] + user_histories[chat_id])
                    user_histories[chat_id].append({"role": "assistant", "content": reply})
                    send_message(chat_id, reply)
                except Exception as e:
                    send_message(chat_id, f"❌ 出错了：{str(e)}")
        except Exception as e:
            logging.error(f"Error: {e}")

if __name__ == "__main__":
    main()
