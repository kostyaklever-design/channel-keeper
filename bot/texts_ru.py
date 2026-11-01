"""Russian lines for the bot's own texts. Key = the English text exactly as in the code (see i18n.py).
A test fails when a text in the code has no line here, or a line here uses other {placeholders}."""

RU: dict[str, str] = {
    # ---------- /setup ----------
    'Step 1 of 2 — which channel do I post to?': 'Шаг 1 из 2 — в какой канал публикую?',
    'Step 1 of 2 — the channel.\nAdd me to your channel as admin with «Post messages», then send /setup again.\n'
    'Already did it? Forward any post from the channel here.':
        'Шаг 1 из 2 — канал.\nДобавьте меня в канал админом с правом «Публикация сообщений» и снова отправьте /setup.\n'
        'Уже добавили? Перешлите сюда любой пост из канала.',
    'Step 2 of 2 — the discussion group (⭐ = linked to the channel):':
        'Шаг 2 из 2 — группа обсуждения (⭐ = привязана к каналу):',
    'Step 2 of 2 — the discussion group.\nAdd me to the group as admin with «Delete messages» and «Ban users», '
    'then send /setup in that group, and /setup here again.':
        'Шаг 2 из 2 — группа обсуждения.\nДобавьте меня в группу админом с правами «Удаление сообщений» и '
        '«Блокировка пользователей», отправьте /setup в этой группе, а потом снова /setup здесь.',
    'Got «{title}».': 'Есть: «{title}».',
    'Got this group. Now open me in a private chat and send /setup.':
        'Группу запомнил. Теперь откройте меня в личке и отправьте /setup.',
    'Pick the channel first: send /setup.': 'Сначала выберите канал: отправьте /setup.',
    'Only the owner can do this.': 'Это может только владелец.',
    'You are the owner of this bot now. Only you can manage it; add more people with ADMIN_IDS in the server variables.':
        'Теперь вы владелец этого бота. Управлять им можете только вы; других людей добавьте через ADMIN_IDS '
        'в переменных сервера.',
    'The channel and the group are set by CHANNEL_ID and GROUP_ID in the server variables. Remove them there to choose here.':
        'Канал и группа заданы переменными сервера CHANNEL_ID и GROUP_ID. Чтобы выбирать здесь, удалите их там.',
    'I am now an admin in «{title}». Send /setup to pick it.': 'Теперь я админ в «{title}». Отправьте /setup, чтобы выбрать.',
    '⚠️ I am no longer an admin in «{title}». Make me admin again, or send /setup to pick another chat.':
        '⚠️ Я больше не админ в «{title}». Верните мне права или отправьте /setup и выберите другой чат.',
    '✅ Channel: can post': '✅ Канал: могу публиковать',
    '⚠️ Channel: turn on «Post messages» for the bot': '⚠️ Канал: включите боту «Публикация сообщений»',
    'ℹ️ Channel: to pin posts, also turn on «Edit messages» (optional)':
        'ℹ️ Канал: чтобы закреплять посты, включите ещё «Редактирование сообщений» (по желанию)',
    'ℹ️ Channel: to delete ad posts on a timer, also turn on «Delete messages» (optional)':
        'ℹ️ Канал: чтобы удалять рекламу по таймеру, включите ещё «Удаление сообщений» (по желанию)',
    'ℹ️ Channel: to get messages and suggested posts sent to the channel, turn on «Manage direct messages» (optional)':
        'ℹ️ Канал: чтобы получать сообщения и предложенные посты каналу, включите «Управление личными сообщениями» '
        '(по желанию)',
    '⚠️ Channel: I am not an admin there ({error})': '⚠️ Канал: я там не админ ({error})',
    '✅ Group: can delete messages': '✅ Группа: могу удалять сообщения',
    '⚠️ Group: turn on «Delete messages» for the bot': '⚠️ Группа: включите боту «Удаление сообщений»',
    '✅ Group: can ban and restrict (captcha, flood)': '✅ Группа: могу банить и ограничивать (капча, флуд)',
    '⚠️ Group: turn on «Ban users» for the bot': '⚠️ Группа: включите боту «Блокировка пользователей»',
    'ℹ️ Group: to check join requests before people get in, also turn on «Add users» (optional)':
        'ℹ️ Группа: чтобы проверять заявки до входа, включите ещё «Добавление участников» (по желанию)',
    '⚠️ Group: I am not an admin there ({error})': '⚠️ Группа: я там не админ ({error})',
    '⚠️ This group is not the discussion group of this channel — comments go elsewhere':
        '⚠️ Эта группа не привязана к каналу как обсуждение — комментарии идут в другое место',
    '✅ Done.': '✅ Готово.',
    'Saved, but fix the ⚠️ lines and send /setup again to check.':
        'Сохранил, но исправьте строки с ⚠️ и снова отправьте /setup для проверки.',
    'Next: send me a post right here to try it, or see /queue.':
        'Дальше: отправьте мне пост прямо сюда, чтобы попробовать, или посмотрите /queue.',
    # ---------- the AI key ----------
    "🤖 AI (optional): a second opinion on newcomers' comments, drafts, news retold in your words. "
    'Needs your own OpenAI or Anthropic key.':
        '🤖 ИИ (по желанию): второе мнение о комментариях новичков, черновики, пересказ новостей своими словами. '
        'Нужен ваш ключ OpenAI или Anthropic.',
    '🤖 AI: on — {provider}, {model} (AI_API_KEY in the server variables).':
        '🤖 ИИ: включён — {provider}, {model} (AI_API_KEY в переменных сервера).',
    '🤖 AI: on — {provider}, {model}. /ai off removes the key.': '🤖 ИИ: включён — {provider}, {model}. /ai off удаляет ключ.',
    '🔑 Add AI key': '🔑 Добавить ключ ИИ',
    '🔑 Replace AI key': '🔑 Заменить ключ ИИ',
    'The AI key is set by AI_API_KEY in the server variables; change it there.':
        'Ключ ИИ задан переменной сервера AI_API_KEY; меняйте его там.',
    'Paste your key — OpenAI (platform.openai.com → API keys) or Anthropic (console.anthropic.com → API Keys). '
    'I delete your message at once and keep the key only on your server.':
        'Вставьте ключ — OpenAI (platform.openai.com → API keys) или Anthropic (console.anthropic.com → API Keys). '
        'Ваше сообщение я сразу удалю, а ключ сохраню только на вашем сервере.',
    'That is not a key (keys start with sk-), so no key was saved. /ai key to try again.':
        'Это не ключ (ключи начинаются с sk-), ничего не сохранил. /ai key — попробовать ещё раз.',
    '⚠️ I could not delete your message with the key — delete it yourself.':
        '⚠️ Не смог удалить ваше сообщение с ключом — удалите его сами.',
    'That looked like an AI key, so I deleted it instead of making a post. To add a key: /setup → 🔑 Add AI key.':
        'Это похоже на ключ ИИ, поэтому я удалил сообщение, а не сделал из него пост. Добавить ключ: /setup → '
        '🔑 Добавить ключ ИИ.',
    'AI_API_KEY in the server variables wins; change the key there.':
        'Главнее переменная сервера AI_API_KEY; меняйте ключ там.',
    'Send the key alone, nothing else in the message. /ai key to try again.':
        'Отправьте только ключ, без другого текста. /ai key — попробовать ещё раз.',
    'Not saved. {error}': 'Не сохранил. {error}',
    '✅ AI is on — {provider}, {model}. Try /ai or ✨ under a post. /ai off removes the key.':
        '✅ ИИ включён — {provider}, {model}. Попробуйте /ai или ✨ под постом. /ai off удаляет ключ.',
    # ---------- the post preview ----------
    '✅ Publish now': '✅ Опубликовать',
    '🗑 Cancel': '🗑 Отмена',
    '🕐 In 1 hour': '🕐 Через час',
    '🌅 Tomorrow {hour}:00': '🌅 Завтра в {hour}:00',
    '🗓 Pick a time': '🗓 Выбрать время',
    '✨ Edit with AI': '✨ Править с ИИ',
    '🔗 Buttons: {n}': '🔗 Кнопки: {n}',
    '📣 Ad label: {state}': '📣 Пометка «реклама»: {state}',
    '📌 Pin: {hours}': '📌 Закреп: {hours}',
    '⏱ Delete: {hours}': '⏱ Удалить: {hours}',
    'on': 'вкл',
    'off': 'выкл',
    'until unpinned': 'пока не открепите',
    '7 days': '7 дней',
    '{n} h': '{n} ч',
    'Write: Button text - https://link': 'Напишите: Текст кнопки - https://ссылка',
    'Cannot read «{line}». Write: Button text - https://link': 'Не понял «{line}». Напишите: Текст кнопки - https://ссылка',
    '«{label}…» is too long for a button — up to 40 characters.': '«{label}…» слишком длинно для кнопки — до 40 символов.',
    'Up to {n} buttons.': 'Не больше {n} кнопок.',
    'Send the time like 18:30 or 03.11 18:30.': 'Напишите время так: 18:30 или 03.11 18:30.',
    'There is no such date or time.': 'Такой даты или времени нет.',
    'That time has passed.': 'Это время уже прошло.',
    'More than a year ahead — pick a closer date.': 'Больше чем на год вперёд — выберите дату поближе.',
    'a photo caption': 'подписи к фото',
    'a post': 'поста',
    'Telegram allows {limit} characters for {what}; this one has {n}. Shorten by {cut}.':
        'Telegram разрешает {limit} символов для {what}; здесь {n}. Сократите на {cut}.',
    # ---------- drafts ----------
    '🗓 To queue': '🗓 В очередь',
    '🗓 Schedule': '🗓 По расписанию',
    '✏️ Add comment': '✏️ Добавить комментарий',
    '🗑 Reject': '🗑 Отклонить',
    "✨ Retell in my channel's words": '✨ Пересказать своими словами',
    'The comment is empty.': 'Комментарий пустой.',
    'The comment is {n} characters, keep it under {limit}.': 'В комментарии {n} символов, нужно меньше {limit}.',
    'With this comment the post is {n} characters; Telegram allows {limit}. Shorten by {cut}.':
        'С этим комментарием в посте {n} символов; Telegram разрешает {limit}. Сократите на {cut}.',
    'from {source}': 'из «{source}»',
    'With your comment on top.': 'С вашим комментарием сверху.',
    '📝 News from «{source}».': '📝 Новость из «{source}».',
    '📝 New post from «{source}».': '📝 Новый пост из «{source}».',
    '📝 Draft «{id}» for {at}.': '📝 Черновик «{id}» на {at}.',
    'Below — exactly how it will look in the channel. Add a line of your own: a bare link says little.':
        'Ниже — ровно так, как будет в канале. Добавьте строку от себя: голая ссылка мало что говорит.',
    'Below — exactly how it will look in the channel. Nothing goes out until you press a button.':
        'Ниже — ровно так, как будет в канале. Ничего не уйдёт, пока вы не нажмёте кнопку.',
    '✅ Published by {who}.': '✅ Опубликовал {who}.',
    '🗓 Approved by {who} — in the queue; goes out when the channel rules allow (/queue).':
        '🗓 Одобрил {who} — в очереди; выйдет, когда позволят правила канала (/queue).',
    '🗓 Approved by {who}. Its time has passed — it goes out within a minute.':
        '🗓 Одобрил {who}. Время уже прошло — выйдет в течение минуты.',
    '🗓 Approved by {who} — goes out {at}.': '🗓 Одобрил {who} — выйдет {at}.',
    '🗑 Rejected by {who}.': '🗑 Отклонил {who}.',
    # ---------- notifications and /log ----------
    'Nothing yet.': 'Пока ничего.',
    'Who: {name} (id {id})': 'Кто: {name} (id {id})',
    'Post: {what}': 'Пост: {what}',
    'Why: {what}': 'Причина: {what}',
    'Message: {text}': 'Сообщение: {text}',
    'Unban': 'Разбанить',
    'Clear warning': 'Снять предупреждение',
    '⚠️ Warned and deleted': '⚠️ Предупреждён, сообщение удалено',
    '⛔ Banned and deleted': '⛔ Забанен, сообщение удалено',
    '✅ Unbanned': '✅ Разбанен',
    '✅ Warning cleared': '✅ Предупреждение снято',
    '⛔ Banned by an admin': '⛔ Забанен админом',
    '📣 Published': '📣 Опубликовано',
    '🗓 Draft approved': '🗓 Черновик одобрен',
    '🗑 Draft rejected': '🗑 Черновик отклонён',
    '✏️ Draft commented': '✏️ К черновику добавлен комментарий',
    '📥 New from a feed': '📥 Новое из ленты',
    '✅ Published anyway': '✅ Опубликовано вне очереди',
    '🗑 Skipped from the queue': '🗑 Убрано из очереди',
    "🚪 Removed: did not press «I'm human»": '🚪 Удалён: не нажал «Я человек»',
    '🔇 Read-only for flooding': '🔇 Только чтение за флуд',
    '⏳ Deleted: too soon after a post': '⏳ Удалено: слишком рано после поста',
    '🤖 Flagged by AI — waiting for an owner': '🤖 ИИ счёл подозрительным — ждёт решения владельца',
    "🗑 Deleted after an owner's review": '🗑 Удалено по решению владельца',
    '🐣 Deleted: newcomer on probation': '🐣 Удалено: новичок на испытательном сроке',
    '📝 Post suggested to the channel': '📝 Каналу предложили пост',
    '🚪 Join request declined': '🚪 Заявка на вступление отклонена',
    '✅ Suggested post approved': '✅ Предложенный пост одобрен',
    '❌ Suggested post declined': '❌ Предложенный пост отклонён',
    '👤 Profile with an ad — waiting for an owner': '👤 Реклама в профиле — ждёт решения владельца',
    '🧠 Looks like spam you deleted before — waiting for an owner':
        '🧠 Похоже на спам, который вы уже удаляли, — ждёт решения владельца',
    # ---------- /lang and the command menu ----------
    'Language: {name}. Change: /lang ru, /lang en, or /lang auto for your Telegram language.':
        'Язык: {name}. Сменить: /lang ru, /lang en или /lang auto — как в вашем Telegram.',
    'keeper.yaml sets language: {lang}, and it wins over /lang.': 'В keeper.yaml задан language: {lang}, он главнее /lang.',
    '✅ Language: {name}.': '✅ Язык: {name}.',
    'pick the channel and group, check rights': 'выбрать канал и группу, проверить права',
    'what goes out and when': 'что и когда выйдет',
    'drafts waiting for you': 'черновики, которые ждут вас',
    'feeds and their last check': 'ленты и последняя проверка',
    "the channel's week": 'неделя канала',
    'what the bot did': 'что сделал бот',
    'drafts from the AI; /ai key adds the key': 'черновики от ИИ; /ai key — добавить ключ',
    'language: /lang ru, /lang en, /lang auto': 'язык: /lang ru, /lang en, /lang auto',
    'delete everything about a person': 'удалить всё о человеке',
    'chat id and your user id': 'id чата и ваш id',
    'which version is running': 'какая версия запущена',
    'reply to a message to ban its author': 'ответом на сообщение — забанить автора',
    'lift a ban': 'снять бан',
    # ---------- posts from the private chat ----------
    'A post is text, a photo, a video, a GIF, or an album of photos and videos.':
        'Пост — это текст, фото, видео, GIF или альбом из фото и видео.',
    'GIFs cannot be in an album — send the GIF on its own.': 'GIF нельзя добавить в альбом — отправьте GIF отдельно.',
    'Up to {n} photos and videos in an album.': 'В альбоме не больше {n} фото и видео.',
    '👀 Preview — exactly how it will look in the channel:': '👀 Превью — ровно так, как будет в канале:',
    '{what} — the updated preview:': '{what} — обновлённое превью:',
    '📌 pinned ({hours})': '📌 закреплён ({hours})',
    '⚠️ not pinned: the bot needs «Edit messages» in the channel ({error})':
        '⚠️ не закреплён: боту нужно право «Редактирование сообщений» в канале ({error})',
    '⏱ goes away in {n} h (the bot needs «Delete messages» in the channel for that)':
        '⏱ удалится через {n} ч (для этого боту нужно право «Удаление сообщений» в канале)',
    '⚠️ Could not unpin post {id} in the channel: {error}.': '⚠️ Не смог открепить пост {id} в канале: {error}.',
    '⚠️ Could not delete post {id} in the channel: {error}.': '⚠️ Не смог удалить пост {id} в канале: {error}.',
    "Check the bot's rights there (Edit / Delete messages).":
        'Проверьте права бота там (редактирование / удаление сообщений).',
    'Only the channel owners can do this.': 'Это могут только владельцы канала.',
    'Already done.': 'Уже сделано.',
    'Publishing…': 'Публикую…',
    '✅ Published.': '✅ Опубликовано.',
    'Could not publish: {why}. The post is still here.': 'Не получилось опубликовать: {why}. Пост остался здесь.',
    '🗑 Cancelled — nothing goes to the channel.': '🗑 Отменено — в канал ничего не уйдёт.',
    'Telegram does not allow buttons under an album. Send one photo or video for a post with buttons.':
        'Telegram не разрешает кнопки под альбомом. Для поста с кнопками отправьте одно фото или видео.',
    'Buttons under the post, one per line (up to 3):\nBuy now - https://example.com/shop\nSend «-» to remove them.':
        'Кнопки под постом, по одной в строке (до 3):\nКупить - https://example.com/shop\nОтправьте «-», чтобы убрать их.',
    'Text - https://…': 'Текст - https://…',
    'What should the AI change? For example: shorter, add a question at the end, in Dutch.':
        'Что ИИ поменять? Например: короче, добавить вопрос в конце, на английском.',
    'shorter': 'короче',
    'When? For example 18:30 or {day} 09:00 ({zone}).': 'Когда? Например 18:30 или {day} 09:00 ({zone}).',
    '🗓 Goes out {at}. It is in /queue; the buttons above still work.':
        '🗓 Выйдет {at}. Пост в /queue; кнопки выше по-прежнему работают.',
    'That post is already done — nothing changed.': 'С этим постом уже всё — ничего не изменилось.',
    'the bot was offline': 'бот был выключен',
    '⚠️ It was due {at} and did not go out ({why}). Publish it now?':
        '⚠️ Пост должен был выйти {at}, но не вышел ({why}). Опубликовать сейчас?',
    '✅ Published on time.': '✅ Опубликовано вовремя.',
    'Your scheduled post': 'Ваш запланированный пост',
    '⚠️ Not published: {why}. Fix it and press Publish now.':
        '⚠️ Не опубликовано: {why}. Исправьте и нажмите «Опубликовать».',
    '• {at} «{text}» (from the private chat)': '• {at} «{text}» (из лички)',
    'photo': 'фото',
    # ---------- drafts ----------
    'The draft «{id}»': 'Черновик «{id}»',
    '⌛ Expired: no answer in 48 hours.': '⌛ Истёк: 48 часов без ответа.',
    '⌛ Expired: no answer in 48 hours. Change its id in posts.yaml to send it again.':
        '⌛ Истёк: 48 часов без ответа. Чтобы прислать снова, поменяйте его id в posts.yaml.',
    'Only admins can do this.': 'Это могут только админы.',
    'Already decided.': 'Уже решено.',
    'This post is no longer in posts.yaml.': 'Этого поста больше нет в posts.yaml.',
    'Reply with 1–2 lines for «{id}». They go on top of the post, and you get a new preview.':
        'Ответьте 1–2 строками для «{id}». Они встанут над постом, а вы получите новое превью.',
    'Your comment': 'Ваш комментарий',
    'Could not publish «{id}»: {why}. The draft is still open.':
        'Не получилось опубликовать «{id}»: {why}. Черновик остаётся открытым.',
    'Held by the channel rules': 'Придержано правилами канала',
    '🗓 Approved by {who} — in the queue: {why}.': '🗓 Одобрил {who} — в очереди: {why}.',
    'Could not publish «{id}»: {why}. It waits in the queue.':
        'Не получилось опубликовать «{id}»: {why}. Ждёт в очереди.',
    'That draft is already decided — nothing changed.': 'По этому черновику уже решено — ничего не изменилось.',
    'Send it again.': 'Отправьте ещё раз.',
    '✏️ Comment added by {who} — new preview below.': '✏️ {who} добавил комментарий — новое превью ниже.',
    'removed from posts.yaml': 'удалён из posts.yaml',
    'waiting for you': 'ждёт вас',
    'approved': 'одобрен',
    '(with comment)': '(с комментарием)',
    'No open drafts.': 'Открытых черновиков нет.',
    # ---------- the queue and the channel rules ----------
    'quiet hours until {at}': 'тихие часы до {at}',
    '{n} posts today, the limit is {limit} — tomorrow': 'сегодня уже {n} постов, лимит {limit} — завтра',
    'rule 1 : {limit}: {n} news in a row — waits for your own post':
        'правило 1 : {limit}: {n} новостей подряд — ждёт вашего поста',
    '{n} min between posts — after {at}': '{n} мин между постами — после {at}',
    '✅ Publish anyway': '✅ Опубликовать всё равно',
    '🗑 Skip': '🗑 Пропустить',
    '⏸ «{name}» waits in the queue: {why}.': '⏸ «{name}» ждёт в очереди: {why}.',
    '⌛ Left the queue: older than 72 hours.': '⌛ Убрано из очереди: старше 72 часов.',
    '✅ Went out on its own — the rules allowed it.': '✅ Вышло само — правила разрешили.',
    '«{name}» from the queue': '«{name}» из очереди',
    'Could not publish «{id}»: {why}. It stays in the queue.':
        'Не получилось опубликовать «{id}»: {why}. Остаётся в очереди.',
    '✅ Published anyway by {who}.': '✅ {who} опубликовал вне очереди.',
    '🗑 Skipped by {who}.': '🗑 {who} пропустил.',
    'next, within a minute': 'следующий, в течение минуты',
    'after the posts above': 'после постов выше',
    'news': 'новость',
    'own': 'своё',
    'Queue: {n}': 'Очередь: {n}',
    'Queue: empty': 'Очередь: пусто',
    'Today in the channel: {n} of {limit}': 'Сегодня в канале: {n} из {limit}',
    'Today in the channel: {n}': 'Сегодня в канале: {n}',
    'Quiet hours: {start}–{end}': 'Тихие часы: {start}–{end}',
    'Rule 1 : {n}: at most {n} news in a row': 'Правило 1 : {n}: не больше {n} новостей подряд',
    '(draft)': '(черновик)',
    'Next from posts.yaml:': 'Дальше из posts.yaml:',
    'Scheduled from the private chat:': 'Запланировано из лички:',
    # ---------- the inbox ----------
    'someone': 'кто-то',
    "(no text — open the channel's messages in Telegram)": '(без текста — откройте сообщения канала в Telegram)',
    '📝 Suggested post from {name} — offers {price}': '📝 {name} предлагает пост — за {price}',
    '📝 Suggested post from {name} (free)': '📝 {name} предлагает пост (бесплатно)',
    '✅ Approve': '✅ Одобрить',
    '❌ Decline': '❌ Отклонить',
    '✉️ {name} wrote to the channel:': '✉️ {name} написал каналу:',
    '↩️ Reply': '↩️ Ответить',
    'Only the owners can do this.': 'Это могут только владельцы.',
    'Your answer to {name} — it goes from the channel. Reply to this message:':
        'Ваш ответ для {name} — уйдёт от имени канала. Ответьте на это сообщение:',
    'Your answer': 'Ваш ответ',
    '✅ Approved by {who} — Telegram publishes it in the channel.': '✅ Одобрил {who} — Telegram опубликует пост в канале.',
    'Already handled in Telegram or expired ({error}).': 'Уже решено в Telegram или истекло ({error}).',
    '⚠️ Telegram refused: {error}. Does the bot have «Manage direct messages» and «Post messages»?':
        '⚠️ Telegram отказал: {error}. Есть ли у бота права «Управление личными сообщениями» и «Публикация сообщений»?',
    '❌ Declined by {who}.': '❌ Отклонил {who}.',
    '⚠️ Telegram refused: {error}.': '⚠️ Telegram отказал: {error}.',
    "Only text can be sent as the channel's answer. Write it, or press ↩️ Reply again later.":
        'Ответом от канала можно отправить только текст. Напишите его или нажмите ↩️ Ответить позже.',
    'That conversation is gone — nothing sent.': 'Этого разговора уже нет — ничего не отправлено.',
    'Not sent: {error}. Does the bot have «Manage direct messages» in the channel?':
        'Не отправлено: {error}. Есть ли у бота право «Управление личными сообщениями» в канале?',
    '↩️ Sent to {name} from the channel.': '↩️ Отправлено {name} от имени канала.',
    'Inbox: unanswered messages {m}, suggested posts {s}': 'Входящие: без ответа {m}, предложенных постов {s}',
    # ---------- moderation and owners' commands ----------
    'message on behalf of a channel': 'сообщение от имени канала',
    '{reason} (added by editing)': '{reason} (добавлено правкой)',
    'forward from another channel': 'пересылка из другого канала',
    'link': 'ссылка',
    'disguised link': 'замаскированная ссылка',
    'spam word "{word}"': 'стоп-слово «{word}»',
    '{n} messages in {s} s — read-only for {m} min': '{n} сообщений за {s} с — только чтение на {m} мин',
    'within {n} min of a post': 'в первые {n} мин после поста',
    'a forward': 'пересылка',
    'a contact': 'контакт',
    'a story': 'история',
    'a message with buttons': 'сообщение с кнопками',
    'a picture or video without words': 'картинка или видео без текста',
    '{what} before {n} messages': '{what} раньше {n} сообщений',
    '{reason} in the profile': '{reason} в профиле',
    '👤 Newcomer with {why}.': '👤 Новичок: {why}.',
    '→ banned after a second violation': '→ забанен после второго нарушения',
    "Reply to the spammer's message with /ban.": 'Ответьте на сообщение спамера командой /ban.',
    '→ banned by an admin': '→ забанен админом',
    'by /ban': 'командой /ban',
    'Use /unban <user or channel id> or reply to a message with /unban.':
        'Напишите /unban <id человека или канала> или ответьте на сообщение командой /unban.',
    '→ unbanned by an admin': '→ разбанен админом',
    'by /unban': 'командой /unban',
    'Channel {id} can write again.': 'Канал {id} снова может писать.',
    'User {id} can write again.': 'Пользователь {id} снова может писать.',
    'chat id: {chat}\nyour user id: {user}': 'id чата: {chat}\nваш id: {user}',
    'button': 'кнопкой',
    '✅ Unbanned by {who} — they can join again.': '✅ {who} разбанил — можно снова вступать.',
    '✅ Warning cleared by {who}.': '✅ {who} снял предупреждение.',
    '⚠️ «{id}» from posts.yaml was due {at} and did not go out ({why}). It is skipped — change its id and time to '
    'send it again.':
        '⚠️ «{id}» из posts.yaml должен был выйти {at}, но не вышел ({why}). Пропускаю — чтобы отправить снова, '
        'поменяйте его id и время.',
    '«{id}» from posts.yaml': '«{id}» из posts.yaml',
    'Use /forget 123456789 (a user or channel id — see /log).': 'Напишите /forget 123456789 (id человека или канала — см. /log).',
    'Deleted {n} records about {id}: warnings, captcha, log lines. A ban in Telegram itself stays — use /unban for that.':
        'Удалено записей о {id}: {n} — предупреждения, капча, журнал. Бан в самом Telegram остаётся — для этого /unban.',
    # ---------- the captcha and join requests (the person's own language) ----------
    'This button is for someone else.': 'Эта кнопка для другого человека.',
    'Thanks! You can write now.': 'Спасибо! Теперь можно писать.',
    'Thanks! The admins will let you write shortly.': 'Спасибо! Админы скоро разрешат вам писать.',
    "⚠️ {name} pressed «I'm human», but the bot could not give their rights back — lift the restriction in the "
    'group by hand (id {id}).':
        '⚠️ {name} нажал «Я человек», но бот не смог вернуть ему права — снимите ограничение в группе вручную (id {id}).',
    'joined': 'вступил',
    'first message': 'первое сообщение',
    '🚪 {name} (id {id}) asks to join the group — {why}.': '🚪 {name} (id {id}) просится в группу — {why}.',
    'Profile: {bio}': 'Профиль: {bio}',
    'please decide': 'решите сами',
    'the bot could not send them the button': 'бот не смог отправить ему кнопку',
    'To join «{title}», press the button within 4 minutes.': 'Чтобы вступить в «{title}», нажмите кнопку в течение 4 минут.',
    'Too late — send the request again.': 'Поздно — отправьте заявку ещё раз.',
    'Welcome!': 'Добро пожаловать!',
    'Something went wrong — the admins will see your request.': 'Что-то пошло не так — админы увидят вашу заявку.',
    '✅ Welcome — you can write in the group now.': '✅ Добро пожаловать — теперь можно писать в группе.',
    'Your request is waiting for the admins.': 'Ваша заявка ждёт админов.',
    '✅ Approved by {who}.': '✅ Одобрил {who}.',
    'Already handled (in the app, or the request expired).': 'Уже решено (в приложении или заявка истекла).',
    'join request': 'заявка на вступление',
    'no press in time': 'не нажал вовремя',
    '⌛ Time is up. Send the join request again to try once more.': '⌛ Время вышло. Отправьте заявку ещё раз, чтобы попробовать снова.',
    # ---------- reviews and the learning filter ----------
    '🗑 Delete': '🗑 Удалить',
    '✅ Keep': '✅ Оставить',
    'It is still in the chat — your call.': 'Сообщение пока в чате — решать вам.',
    '🧠 Looks like spam you deleted before ({n}%).': '🧠 Похоже на спам, который вы уже удаляли ({n}%).',
    'Already decided by another owner.': 'Уже решил другой владелец.',
    '🗑 Deleted by {who}.': '🗑 Удалил {who}.',
    'Already gone.': 'Уже удалено.',
    'an owner agreed it is spam': 'владелец подтвердил, что это спам',
    '✅ Kept by {who}; this person is trusted now — no more checks of this kind.':
        '✅ {who} оставил; этому человеку теперь доверяем — таких проверок больше не будет.',
    'on — learned from {spam} spam and {ok} kept messages': 'включён — обучен на {spam} спам и {ok} нормальных сообщениях',
    'learning — {spam}/{need} spam, {ok}/{need} kept (press Keep on reviews to teach it)':
        'учится — спам {spam}/{need}, нормальных {ok}/{need} (нажимайте «Оставить» в проверках, чтобы учить)',
    # ---------- /report ----------
    '📊 Channel week': '📊 Неделя канала',
    'Posts: {total} — {own} yours, {news} news from others': 'Постов: {total} — ваших {own}, чужих новостей {news}',
    'balanced': 'в балансе',
    "too many others' news — post something of your own": 'слишком много чужих новостей — опубликуйте что-то своё',
    'Rule 1 : {n}: {ratio}': 'Правило 1 : {n}: {ratio}',
    'Right now {n} news in a row: the next news waits for your post':
        'Сейчас {n} новостей подряд: следующая ждёт вашего поста',
    'Cleaned up:': 'Убрано:',
    '• nothing — a quiet week': '• ничего — спокойная неделя',
    'Drafts waiting for you: {n} (/drafts)': 'Черновиков ждут вас: {n} (/drafts)',
    'Learning filter: {state}': 'Обучаемый фильтр: {state}',
    'AI this month: {calls} of {limit} requests, {tokens} tokens': 'ИИ в этом месяце: {calls} из {limit} запросов, {tokens} токенов',
    'warnings': 'предупреждений',
    'bans': 'банов',
    'bans by admins': 'банов админами',
    'removed by captcha': 'удалено капчей',
    'muted for flood': 'ограничено за флуд',
    'held in fresh posts': 'придержано в свежих постах',
    'flagged by AI': 'отмечено ИИ',
    'flagged for the profile': 'отмечено за профиль',
    'flagged by the learning filter': 'отмечено обучаемым фильтром',
    'deleted after your review': 'удалено после вашей проверки',
    'deleted after your review (before 1.8.6)': 'удалено после вашей проверки (до 1.8.6)',
    # ---------- feeds ----------
    'cannot reach the feed: {error}': 'лента недоступна: {error}',
    'the feed answered {code} — check the address': 'лента ответила {code} — проверьте адрес',
    'the feed answered {code}': 'лента ответила {code}',
    'the feed is larger than 5 MB': 'лента больше 5 МБ',
    'this address is not an RSS or Atom feed': 'по этому адресу нет ленты RSS или Atom',
    'No sources. Add them to sources.yaml — see docs/SOURCES.md.': 'Лент нет. Добавьте их в sources.yaml — см. docs/SOURCES.md.',
    'Sources: {n}, checked every {m} min': 'Лент: {n}, проверка каждые {m} мин',
    'draft': 'черновик',
    'auto': 'сразу',
    'waiting for the first check': 'ждёт первой проверки',
    'last good {at}': 'последний раз успешно {at}',
    'checked {at}, getting ready': 'проверена {at}, готовится',
    '✓ {at} · brought in {found} · skipped {skipped}': '✓ {at} · принесено {found} · пропущено {skipped}',
    # ---------- the AI ----------
    '🤖 Looks like spam ({n}%: {why}).': '🤖 Похоже на спам ({n}%: {why}).',
    'no reason given': 'без объяснения',
    'Cannot open the link ({error}).': 'Не открывается ссылка ({error}).',
    'The key is set by AI_API_KEY in the server variables; remove it there.':
        'Ключ задан переменной сервера AI_API_KEY; удалите его там.',
    '🗑 The AI key is removed. AI is off.': '🗑 Ключ ИИ удалён. ИИ выключен.',
    'There was no key.': 'Ключа и не было.',
    'Tell me what you need, for example:\n/ai 3 short posts from https://example.com/article\n'
    '/ai a post about our new feature: …\n/ai what should we post tomorrow?\n\n'
    '/ai key — add or replace your AI key; /ai off — remove it.':
        'Напишите, что нужно, например:\n/ai 3 коротких поста по https://example.com/article\n'
        '/ai пост о нашей новой функции: …\n/ai что опубликовать завтра?\n\n'
        '/ai key — добавить или заменить ключ ИИ; /ai off — удалить его.',
    'AI is off. Add your OpenAI or Anthropic key: /ai key (or /setup → 🔑 Add AI key).':
        'ИИ выключен. Добавьте ключ OpenAI или Anthropic: /ai key (или /setup → 🔑 Добавить ключ ИИ).',
    'AI is off. Add your OpenAI or Anthropic key: /setup → 🔑 Add AI key (or AI_API_KEY in the server variables).':
        'ИИ выключен. Добавьте ключ OpenAI или Anthropic: /setup → 🔑 Добавить ключ ИИ (или AI_API_KEY в переменных сервера).',
    'The AI returned nothing usable. Try asking differently.': 'ИИ не вернул ничего полезного. Попробуйте сформулировать иначе.',
    'The AI returned nothing usable.': 'ИИ не вернул ничего полезного.',
    'The AI returned nothing usable — the draft is unchanged.': 'ИИ не вернул ничего полезного — черновик не изменился.',
    '✨ Drafts below: {n}. Nothing goes to the channel until you press a button; edit them with ✨ or write your own.':
        '✨ Черновиков ниже: {n}. В канал ничего не уйдёт, пока вы не нажмёте кнопку; правьте через ✨ или напишите свой.',
    '✨ Draft from the AI:': '✨ Черновик от ИИ:',
    'Write in words what to change — for example «shorter».': 'Напишите словами, что поменять, — например «короче».',
    'That post is gone — nothing changed.': 'Этого поста уже нет — ничего не изменилось.',
    '✨ New version. The old version is still scheduled — cancel it with 🗑 under it if you use this one.':
        '✨ Новая версия. Старая всё ещё запланирована — отмените её кнопкой 🗑 под ней, если берёте эту.',
    '✨ New version. The old one is still above.': '✨ Новая версия. Старая осталась выше.',
    'This draft is already decided.': 'По этому черновику уже решено.',
    'AI is off: add your key with /ai key.': 'ИИ выключен: добавьте ключ командой /ai key.',
    '✨ Retold by the AI — the new preview is below.': '✨ ИИ пересказал — новое превью ниже.',
    '✨ Written from the headline only (the feed has no article text). Check it before publishing — the new preview '
    'is below.':
        '✨ Написано только по заголовку (в ленте нет текста статьи). Проверьте перед публикацией — новое превью ниже.',
    'Retelling…': 'Пересказываю…',
    'The monthly AI limit ({n} requests) is reached. Raise AI_MONTHLY_LIMIT or wait for the next month.':
        'Месячный лимит ИИ ({n} запросов) исчерпан. Поднимите AI_MONTHLY_LIMIT или дождитесь следующего месяца.',
    'Cannot reach the AI provider ({error}).': 'Не удаётся связаться с провайдером ИИ ({error}).',
    'The AI provider ({provider}) refused the key: {error} Check the key, and that it may use the model {model}.':
        'Провайдер ИИ ({provider}) не принял ключ: {error} Проверьте ключ и что ему доступна модель {model}.',
    'The AI provider answered {code}: {error}': 'Провайдер ИИ ответил {code}: {error}',
    # ---------- publishing failures ----------
    'unknown error — see the log': 'неизвестная ошибка — смотрите лог',
    'the bot has no right to post in the channel — channel → Administrators → the bot → «Post messages» ({error})':
        'у бота нет права публиковать в канале — канал → Администраторы → бот → «Публикация сообщений» ({error})',
    'the bot is not an admin of the channel, or CHANNEL_ID is wrong ({error})':
        'бот не админ канала или CHANNEL_ID указан неверно ({error})',
    'the formatting of the text is broken ({error})': 'сломано форматирование текста ({error})',
    'Telegram asked to slow down — try again in a minute ({error})': 'Telegram просит притормозить — попробуйте через минуту ({error})',
    '⚠️ Cannot publish to the channel: {why}. Posts wait until this is fixed.':
        '⚠️ Не могу публиковать в канал: {why}. Посты ждут, пока это не исправят.',
    '⚠️ {what} was not published after {n} tries: {why}. It is set aside.':
        '⚠️ {what} — не опубликовано после {n} попыток: {why}. Отложено.',
    'no channel chosen yet — send /setup': 'канал ещё не выбран — отправьте /setup',
    'the picture {name} is missing': 'картинки {name} нет',
    '⬆️ The album above': '⬆️ Альбом выше',
    # ---------- what the chat and the channel read by default (keeper.yaml can replace each) ----------
    '{name}, links and ads are not allowed here. Next time it is a ban.':
        '{name}, ссылки и реклама здесь запрещены. В следующий раз — бан.',
    '{name} was removed for repeated spam.': '{name} удалён за повторный спам.',
    '{name}, too many messages in a row — you can write again in a few minutes.':
        '{name}, слишком много сообщений подряд — писать снова можно через несколько минут.',
    '{name}, new members can comment a few minutes after a post.':
        '{name}, новые участники могут комментировать через несколько минут после поста.',
    '{name}, pictures without words, forwards and contacts open up after your first few messages.':
        '{name}, картинки без текста, пересылки и контакты станут доступны после первых сообщений.',
    '{name}, press the button within {seconds} seconds to write in this chat.':
        '{name}, нажмите кнопку в течение {seconds} секунд, чтобы писать в этом чате.',
    "I'm human": 'Я человек',
    'Advertisement': 'Реклама',
    'Read on {source} →': 'Читать на {source} →',
    'Cannot read the link (answer {code}).': 'Не читается ссылка (ответ {code}).',
}
