# Переменные окружения (Railway → сервис → Variables)

[English](CONFIG.md)

Обязательна только `BOT_TOKEN`: канал, группу и владельцев можно выбрать в Telegram через `/setup`. Если задать их здесь, главнее переменные. Всё остальное — часовой пояс, стоп-слова, тексты бота в чате — в [keeper.yaml](SETTINGS.ru.md).
Ниже — каждая переменная, которую читает бот; сторож `tests/test_docs.py` сверяет английскую таблицу с кодом.

| Переменная | Обязательна | Что это | Пример |
| --- | --- | --- | --- |
| `BOT_TOKEN` | да | Токен бота от @BotFather. Никому не показывайте. | `123456:ABC...` |
| `CHANNEL_ID` | нет | Id канала. Пусто — выбирается в `/setup` | `-1001234567890` |
| `GROUP_ID` | нет | Id группы обсуждения. Пусто — выбирается в `/setup` | `-1009876543210` |
| `ADMIN_IDS` | нет | Telegram-id владельцев через запятую. Пусто — владельцем станет первый, кто отправит `/setup` | `123456789` |
| `DATA_DIR` | нет | Папка памяти бота. По умолчанию `/data` — подключите туда том Railway | `/data` |
| `CONTENT_REPO` | нет | Приватный репозиторий GitHub с `posts.yaml`, `keeper.yaml` и картинками. Пусто — файлы из этого репозитория | `yourname/channel-content` |
| `CONTENT_TOKEN` | с `CONTENT_REPO` | Fine-grained токен GitHub: только этот репозиторий, только **Contents: Read** | `github_pat_...` |
| `CONTENT_BRANCH` | нет | Ветка репозитория с контентом. По умолчанию `main` | `main` |
| `AI_API_KEY` | нет | Ваш ключ Anthropic или OpenAI. Пусто — без ИИ, или ключ, добавленный в Telegram через `/setup` → 🔑 Добавить ключ ИИ. См. [AI](AI.ru.md) | `sk-ant-...` |
| `AI_PROVIDER` | нет | `anthropic` или `openai`. Пусто — определяется по ключу (`sk-ant-…` = anthropic) | `openai` |
| `AI_MODEL` | нет | Название модели. По умолчанию: `claude-haiku-5-5` (anthropic), `gpt-5-nano` (openai) | `gpt-5-nano` |
| `AI_MONTHLY_LIMIT` | нет | Не больше стольких запросов к ИИ за календарный месяц (по умолчанию 300) — бережёт ваш счёт | `300` |
| `CONTENT_DIR` | нет | Локальная папка с контентом, когда `CONTENT_REPO` пуст. По умолчанию — корень репозитория | `.` |

## Контент в отдельном приватном репозитории (по желанию)
Контент-план остаётся приватным, даже если код бота открыт, а правки не пересобирают бота.

1. GitHub → **New repository** → имя, например `channel-content` → **Private** → Create.
2. Загрузите `posts.yaml`, `keeper.yaml` и папку `posts` с картинками.
3. GitHub → ваш аватар → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.
   Repository access: **Only select repositories** → `channel-content`. Permissions → **Contents: Read-only**. Создайте, скопируйте.
4. Railway → Variables: `CONTENT_REPO` = `yourname/channel-content`, `CONTENT_TOKEN` = токен.
5. В течение 5 минут бот начнёт читать контент оттуда. В логе появится `content from github:...`.
