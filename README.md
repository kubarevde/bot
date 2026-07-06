# Worktime Bot

Телеграм-бот учёта рабочего времени с записью в Google Sheets.

## Быстрый старт (локально)

1. Клонируйте репозиторий
2. Установите зависимости: `pip install -r requirements.txt`
3. Скопируйте `.env.example` в `.env` и заполните значения
4. Положите `service_account.json` в папку `credentials/`
5. Запустите: `python bot.py`

## Деплой на Bothost

1. Создайте репозиторий на GitHub и залейте код
2. В панели Bothost при создании бота укажите Git URL
3. В переменных окружения Bothost добавьте:
   - `BOT_TOKEN` — токен бота
   - `GOOGLE_SHEETS_NAME` — название таблицы
   - `GOOGLE_CREDS_JSON` — содержимое `service_account.json` одной строкой

## Структура проекта

```
worktime_bot/
├── bot.py                  # Точка входа
├── requirements.txt        # Зависимости
├── .env                    # Секреты (НЕ заливать на GitHub!)
├── .env.example            # Шаблон (можно заливать)
├── .gitignore              # Что исключить из Git
├── credentials/            # JSON-ключ Google (НЕ заливать на GitHub!)
│   └── service_account.json
└── app/
    ├── config.py           # Настройки из env
    ├── handlers/           # Хэндлеры команд бота
    └── services/
        └── sheets.py       # Клиент Google Sheets
```
