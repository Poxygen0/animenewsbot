# Anime News Bot

A simple Telegram bot that fetches the latest anime news and sends it to a channel.

## Features
- Fetch the latest anime news
- Post the latest news to a specified Telegram channel
- Built with Python and python-telegram-bot library

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Poxygen0/animenewsbot.git
   cd animenewsbot
   ```

2. Install dependencies in a preferred virtual env:
   ```bash
   pip3 install -r requirements.txt
   ```

3. Create a .env file with the following variables:
   ```env
   BOT__TOKEN = 'Your_token_here'
   DATABASE__URL = "sqlite:///data/database/botdata.db"
   BOT__OWNER_ID = 'Your_user_id_here'
   BOT__USERNAME = 'bot_username_here'
   BOT__LOG_CHANNEL_ID = 'logs_channel_id'
   ```
## Run the bot

```bash
python main.py
```

### Pull Requests are welcomed