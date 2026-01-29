# Trading AI Telegram Bot

## Обзор
Это Telegram-бот, который сочетает нейросетевой движок (OpenAI + TradingView) с набором из ~15 технических индикаторов, чтобы выдавать понятные сигналы по бинарным опционам и OTC-активам. Бот прокладывает путь от регистрации на Pocket Option до выдачи сигнала, оборачивая всё дружелюбными сообщениями, кнопками и, при включённом стиле `screenshot`, скриншотами графика.

## Ключевые файлы
- `bot/handlers/start.py` — стартовое приветствие и onboarding.
- `bot/handlers/activation.py` — логика активации + работа с postback-данными.
- `bot/handlers/workspace.py` — выбор пары, анализ и показ сигнала.
- `docs/pocketoption_postback.md` — инструкция по настройке вебхуков PocketOption.
- `bot/services/pocketoption/*` — хранение статусов и HTTP-сервер постбэка.
- `start.sh`, `Dockerfile`, `docker-compose.yml`, `deploy.sh` — запуск локально/в контейнере и деплой.

## Что делает бот
- При старте здоровается и объясняет ключевые идеи: не чудо, а инструмент, помогающий получить торговый сигнал и следить за новостным фоном (`bot/handlers/start.py`).
- Верифицирует пользователя через Pocket Option postback-сервер: проверяет регистрацию + депозит (по умолчанию минимум $50) и предлагает пошаговые инструкции и кнопку для повторной проверки (`bot/handlers/activation.py`, `docs/pocketoption_postback.md`).
- После активации открывает рабочую область, где пользователь выбирает пару → время экспирации → получает детальный сигнал (текст или скриншот + вероятность выигрыша + индикаторы) (`bot/handlers/workspace.py`).
- Хранит список пользователей и одобренных заявок на диске (`bot/services/user_store.py`, `bot/services/approved_store.py`), а статусы Pocket Option обновляются благодаря постбэку (`bot/services/pocketoption/store.py`).

## Быстрый старт
1. Убедитесь, что на сервере установлен Python 3.12 и доступен `pip`. В корне проекта выполните `pip install -r requirements.txt`.
2. Скопируйте `.env.example` (если есть) в `.env` и заполните ключи из секции «Конфигурация» ниже.
3. Запустите:
   - `./start.sh` — запускает одновременно postback-сервер и Telegram-бот.
   - В контейнере/сервере придётся держать открытым порт `POCKETOPTION_POSTBACK_PORT` (по умолчанию 9009). В Docker Compose он пробрасывается наружу как `POCKETOPTION_POSTBACK_HOST_PORT` (по умолчанию 9109).
4. Для продакшена можно воспользоваться `docker-compose up --build` (файл `docker-compose.yml` создаёт сервис `tradingbot`, монтирует `./data`, пробрасывает порт и логирует).
5. Альтернатива: `deploy.sh` синхронизирует проект по rsync на хост `195.179.193.173` и делает `docker compose up -d` на сервере (скрипт уже создаёт `.env`-шаблон и рестартует контейнер).

## Конфигурация (примеры переменных окружения)
| Переменная | Что задаёт | Пример | По умолчанию |
|------------|------------|--------|--------------|
| `BOT_TOKEN` | Токен Telegram-бота (обязательно). | `123:ABC` | — |
| `SUPPORT_USERNAME` | Ник поддержки, отображается в текстах. | `FominovTrade` | `FominovTrade` |
| `PO_REGISTER_URL` | Реферальная ссылка на Pocket Option. | `https://stocks-n-stuff.cash/register` | то же |
| `POCKETOPTION_MIN_DEPOSIT_USD` | Минимальный депозит для подтверждения активации. | `100` | `50.0` |
| `POCKETOPTION_POSTBACK_SECRET` | Общий токен для incoming POST/GET от Pocket Option (обязательно). | `some-long-secret` | — |
| `POCKETOPTION_POSTBACK_PATH` | Путь на postback-сервере (`/pocketoption/postback`). | `/po/postback` | `/pocketoption/postback` |
| `POCKETOPTION_POSTBACK_PORT` | Порт для локального HTTP-сервера (по умолчанию 9009). | `9009` | `9009` |
| `POCKETOPTION_POSTBACK_HOST_PORT` | Куда пробрасывать порт в Docker Compose. | `9109` | `9109` |
| `POCKETOPTION_STORE_PATH` | Выходной файл с данными регистрации/депозита. | `./data/pocketoption_store.json` | то же |
| `POCKETOPTION_DEPOSIT_INSTRUCTION_URL/IMAGE` | Ссылки в инструкциях пользователю. | `https://youtu.be/...` | пустые строки |
| `CHARTIMG_API_KEY` | Ключ для ChartImg (если нужно скриншоты) | — | — |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Ключ и модель для подсказок AI. | `gpt-4o-mini` | `gpt-4o-mini` |
| `AI_LOG_DIR`, `AI_LOG_SAVE_JSON`, `AI_DEBUG` | Логирование нейросетевой части (в `./data/ai_logs`). | — | `./data/ai_logs`, `False`, `False` |

> Остальные параметры (например `tv_exchange`, `oanda_*`, `signal_style`) имеют разумные дефолты и могут быть переопределены в `.env`, когда потребуется. Все переменные описаны в `bot/config.py`.

## PocketOption postback и подтверждение активации
1. Запустите сервер `python -m bot.services.pocketoption.postback` (либо используйте `./start.sh`, т.к. он делает это за вас).
2. Настройте редирект или постбэк-страницу, чтобы вызывать `https://<ваш-домен><POCKETOPTION_POSTBACK_PATH>?token=<секрет>` при регистрации/депозите. Примеры payload-ов из `docs/pocketoption_postback.md`:
   ```
   {"event":"registration","pocket_id":"123456"}
   {"event":"deposit","pocket_id":"123456","deposit":57.2}
   ```
3. Сервер сохраняет данные в `POCKETOPTION_STORE_PATH`. Бот при входе пользователя сначала проверяет регистрацию, потом депозит, и если всё сходится, выдаёт кнопку перехода в рабочую область.
4. Если депозит ниже порога, бот показывает инструкцию, фиксирует `deposit_message_ids` (чтобы затем их удалить) и предлагает снова нажать кнопку «Проверить депозит».

## Рабочая область
1. Пользователь нажимает кнопку «Перейти в рабочую область» (`kb_to_workspace`), бот проверяет, открыт ли рынок (`bot/utils/time_msk.py`).
2. Выбор пары (список меняется в зависимости от режима OTC), затем выбор времени экспирации.
3. После анализа (`bot/services/analysis/analyzer.py`) бот показывает либо текстовый сигнал, либо и дополнительный скриншот (`settings.signal_style == "screenshot"`). Ответ включает:
   - направление тренда (восходящий/нисходящий);
   - вероятность выигрыша/разворота и волатильность;
   - рекомендуемое действие и уровень bull/bear strength;
   - при необходимости называется набор активных индикаторов.
4. Кнопка «Получить новый сигнал» позволяет повторить анализ с теми же настройками.

## Хранилища и логи
- `./data/users.json` и `./data/approved_users.json` хранят чаты, которые уже начали общение или активированы (`bot/services/user_store.py`, `bot/services/approved_store.py`).
- `./data/pocketoption_store.json` содержит дедуплицированные статусы Pocket Option (registration + deposit).
- `./data/ai_logs` хранит дополнительные логи AI: включите `AI_LOG_SAVE_JSON` и `AI_DEBUG` по необходимости.

## Совместимость и контейнер
- `Dockerfile` собирает образ на Python 3.12, устанавливает зависимости из `requirements.txt`, делает `start.sh` исполняемым и запускает всё от пользователя `appuser`.
- `docker-compose.yml` монтирует `./data` и пробрасывает порт `POCKETOPTION_POSTBACK_HOST_PORT`, так чтобы постбэк был доступен извне. Логи ограничены в объёме (10 МБ, 3 файла).
- `deploy.sh` автоматизирует синхронизацию по rsync и запуск `docker compose` на сервере `195.179.193.173`.

## Что дальше
1. Настройте `.env` и убедитесь, что `POCKETOPTION_POSTBACK_SECRET` и `POCKETOPTION_MIN_DEPOSIT_USD` совпадают с бизнес-требованиями.
2. Проведите реальный тест: зарегистрируйтесь через реф ссылку, отправьте ID, убедитесь, что postback от Pocket Option обновляет `pocketoption_store.json`.
3. При необходимости расширьте `bot/services/analysis` или `settings.signal_style`, чтобы объяснять, почему бот рекомендует вход.
