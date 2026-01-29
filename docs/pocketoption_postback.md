# PocketOption постбэк и проверка депозитов

Бот теперь не доверяет заглушке: он вынужден проверять, что пользователь зарегистрировался по реферальной ссылке и после этого пополнил PocketOption минимум на сумму, указанную в `POCKETOPTION_MIN_DEPOSIT_USD`. Для этого:

1. **Настрой переменные окружения** (см. `.env`):
   - `POCKETOPTION_STORE_PATH` — файл, где бот хранит статусы (по умолчанию `./data/pocketoption_store.json`).
   - `POCKETOPTION_POSTBACK_SECRET` — секретный токен, который принимает HTTP-сервер (придумай длинную строку).
   - `POCKETOPTION_POSTBACK_PATH` — путь, на который нужно настроить редирект/постбэк (`/pocketoption/postback` по умолчанию).
   - `POCKETOPTION_POSTBACK_PORT` — порт, на котором будет слушать сервер (по умолчанию `9009`).
   - `POCKETOPTION_DEPOSIT_INSTRUCTION_URL` и `POCKETOPTION_DEPOSIT_INSTRUCTION_IMAGE_URL` — ссылка и изображение инструкции для пользователей.

2. **Запусти сервер постбэка** на своём VPS (домен уже есть). На целевой машине внутри проекта выполни:

```
python -m bot.services.pocketoption.postback
```

Сервер начнёт слушать `http://0.0.0.0:<port><path>` и будет обновлять `pocketoption_store.json` при попадании POST/GET запросов.

3. **Сконфигурируй PocketOption/редирект**:
   - Редирект-страница должна вызывать HTTP-запрос к `https://твой-домен<POCKETOPTION_POSTBACK_PATH>?token=<secret>`.
   - Отправляй JSON `{ "event": "registration", "pocket_id": "123456" }` при подписи нового трейдера, и `{ "event": "deposit", "pocket_id": "123456", "deposit": 57 }` после пополнения.
   - Пример:

```
curl -X POST "https://your-domain.com/pocketoption/postback?token=secret" \
  -H "Content-Type: application/json" \
  -d '{"event":"registration","pocket_id":"123456"}'

curl -X POST "https://your-domain.com/pocketoption/postback?token=secret" \
  -H "Content-Type: application/json" \
  -d '{"event":"deposit","pocket_id":"123456","deposit":57.2}'
```

4. **Что делает бот**:
   - Сохраняет факт регистрации и сумму депозита в `PocketOptionStore`.
   - Когда пользователь отправляет ID, проверяет сначала регистрацию, затем наличие депозита от минимума.
   - Если депозита мало, пишет инструкцию и отправляет кнопку/скриншот (если настроено).
   - Если депозит найден, выдаёт доступ и показывает инструкцию по боту.

5. **Мониторинг**: можно открыть `data/pocketoption_store.json` или логировать сообщения `PocketOption postback` в Docker-логе, чтобы убедиться, что сервер получает данные.

После этих шагов бот перестанет работать от заглушки и сможет подтвердить аккаунт + депозит по реальным данным.
