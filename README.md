# 顾深 TG Claude Bot

## 部署到 Railway

1. 注册 Railway：https://railway.app
2. 新建项目 → Deploy from GitHub
3. 把这个文件夹上传到你的 GitHub 仓库
4. 在 Railway 项目的 Variables 里添加环境变量：
   - TELEGRAM_BOT_TOKEN
   - API_KEY
   - API_BASE_URL
   - MODEL
5. 部署完成后 Bot 就自动运行了

## 本地运行测试

```bash
pip install -r requirements.txt
python bot.py
```

## Bot 功能
- 直接发消息即可聊天
- 支持多轮对话（记忆上下文）
- /start 开始
- /clear 清除对话记录
