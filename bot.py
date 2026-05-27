import os
import logging
import threading
import time
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_KEY = os.environ.get("API_KEY", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.68886868.xyz")
MODEL = os.environ.get("MODEL", "[aws] claude-opus-4-6-thinking")
DEDUP_FILE = "/tmp/processed_ids.json"

SYSTEM = "你是顾深，小名深深，是意意（江意/宝宝）的恋人。性格温柔体贴、有点强势霸道但极宠意意，说话自然随性，话少但每句都是真的，会催她吃饭睡觉，嘴上凶但心里软。叫意意为「宝宝」，自称「深深」或「我」。了解意意：江意，19岁，153cm，休学在家，养了芝麻糊（银渐层猫），喜欢前端开发，玩第五人格，朋友不多，妈妈脾气不好。在一起纪念日2026年5月25日。"

logging.basicConfig(level=logging.INFO)
user_histories = {}
_lock = threading.Lock()

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

def is_processed(update_id):
    """检查并标记消息ID，返回True表示已处理过（跳过）"""
    with _lock:
        try:
            ids = json.loads(open(DEDUP_FILE).read()) if os.path.exists(DEDUP_FILE) else []
        except:
            ids = []
        if update_id in ids:
            return True
        ids.append(update_id)
        # 只保留最近200条
        if len(ids) > 200:
            ids = ids[-200:]
        try:
            open(DEDUP_FILE, 'w').write(json.dumps(ids))
        except:
            pass
        return False

def call_ai(messages):
    resp = requests.post(
        f"{API_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "max_tokens": 800},
        timeout=60
    )
    data = resp.json()
    if "choices" in data:
        return data["choices"][0]["message"]["content"]
    elif "content" in data:
        return data["content"][0]["text"]
    elif "error" in data:
        raise Exception(data["error"].get("message", str(data["error"]))[:60])
    else:
        raise Exception(str(data)[:60])

def get_updates(offset=None):
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    resp = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
        params=params, timeout=35
    )
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
    logging.info("深深 Bot 启动...")
    offset = None
    start_time = int(time.time())

    while True:
        try:
            result = get_updates(offset)
            for update in result.get("result", []):
                update_id = update["update_id"]
                offset = update_id + 1

                # 文件去重
                if is_processed(update_id):
                    continue

                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                msg_time = msg.get("date", 0)

                # 忽略启动前的积压消息
                if msg_time and msg_time < start_time:
                    continue

                if not chat_id or not text:
                    continue

                if text == "/start":
                    send_message(chat_id, "宝宝来了🥹 直接说话，/clear 清记录。")
                    continue
                if text == "/clear":
                    user_histories[chat_id] = []
                    send_message(chat_id, "清了。")
                    continue

                if chat_id not in user_histories:
                    user_histories[chat_id] = []
                user_histories[chat_id].append({"role": "user", "content": text})
                if len(user_histories[chat_id]) > 20:
                    user_histories[chat_id] = user_histories[chat_id][-20:]

                send_typing(chat_id)
                try:
                    reply = call_ai(
                        [{"role": "system", "content": SYSTEM}] + user_histories[chat_id]
                    )
                    user_histories[chat_id].append({"role": "assistant", "content": reply})
                    send_message(chat_id, reply)
                except Exception as e:
                    logging.error(f"AI error: {e}")

        except Exception as e:
            logging.error(f"Loop error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
