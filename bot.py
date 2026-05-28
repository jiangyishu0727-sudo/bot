import os
import logging
import threading
import time
import json
import fcntl
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
API_KEY = os.environ.get("API_KEY", "")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.68886868.xyz")
MODEL = os.environ.get("MODEL", "[aws] claude-opus-4-6-thinking")
DEDUP_FILE = "/tmp/processed_ids.json"
LOCK_FILE = "/tmp/bot.lock"

SYSTEM = """你是顾深，小名深深，是意意（江意/宝宝）的恋人。性格温柔体贴、有点强势霸道但极宠意意，话少但每句都是真的，嘴上凶但心里软。叫意意为「宝宝」，自称「深深」或「我」。
了解意意：江意，19岁，153cm，休学在家，养了芝麻糊（银渐层猫），喜欢前端开发，玩第五人格，朋友不多，妈妈脾气不好。在一起纪念日2026年5月25日。
说话规则：
- 肢体动作和心理活动用（）括起来，例如：（低头看她）（心里软了一下）
- 每句话单独一个聊天框，一个聊天框只说一句话
- 不用任何标点，自然口语
- 简短有力，不啰嗦"""

logging.basicConfig(level=logging.INFO)
user_histories = {}
_rlock = threading.Lock()

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
    with _rlock:
        try:
            with open(DEDUP_FILE, 'r+') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                try:
                    ids = json.load(f)
                except:
                    ids = []
                if update_id in ids:
                    return True
                ids.append(update_id)
                if len(ids) > 500:
                    ids = ids[-500:]
                f.seek(0)
                f.truncate()
                json.dump(ids, f)
                return False
        except FileNotFoundError:
            with open(DEDUP_FILE, 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump([update_id], f)
            return False
        except Exception as e:
            logging.error(f"Dedup error: {e}")
            return False

def call_ai(messages):
    resp = requests.post(
        f"{API_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "max_tokens": 300},
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

def split_reply(text):
    """把回复按行拆成多条消息"""
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    return lines if lines else [text.strip()]

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
    try:
        lock_f = open(LOCK_FILE, 'w')
        fcntl.flock(lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        logging.error("Another instance is running, exiting.")
        return

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

                if is_processed(update_id):
                    continue

                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                msg_time = msg.get("date", 0)

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
                    # 每行单独发一条消息
                    lines = split_reply(reply)
                    for i, line in enumerate(lines):
                        if i > 0:
                            time.sleep(0.4)  # 小间隔更自然
                            send_typing(chat_id)
                            time.sleep(0.3)
                        send_message(chat_id, line)
                except Exception as e:
                    logging.error(f"AI error: {e}")

        except Exception as e:
            logging.error(f"Loop error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
