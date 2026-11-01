"""Newcomers' probation and the profile check.

Probation: until someone has written a few real messages, the bot removes what spammers send first
and honest people rarely need on day one: pictures or videos without a word, forwards, contacts,
messages with buttons from inline bots, stories. Text is not limited — ordinary rules apply.

Profile check: on a newcomer's first message the bot looks at their profile description. A link or
a spam word there is the signature of AI-written «neurocomments» (clean text, the ad sits in the
profile). The bot never bans for it: the message stays and the owners decide.
"""
from .moderation import spam_reason
from .runtime import log, settings, state

TOLD = 'told_probation'      # bot_data: user ids already told about probation


def risky(msg) -> str | None:
    """What in this message is not allowed during probation, or None."""
    if getattr(msg, 'forward_origin', None):
        return 'a forward'
    if getattr(msg, 'contact', None):
        return 'a contact'
    if getattr(msg, 'story', None):
        return 'a story'
    if getattr(msg, 'via_bot', None) or getattr(msg, 'reply_markup', None):
        return 'a message with buttons'
    media = any(getattr(msg, kind, None) for kind in ('photo', 'video', 'animation', 'document', 'video_note'))
    if media and not (getattr(msg, 'caption', None) or '').strip():
        return 'a picture or video without words'
    return None


def on_probation(user_id: int) -> bool:
    p = settings().probation
    return bool(p.messages) and state.clean_count(user_id) < p.messages


def counts(text: str) -> bool:
    """A message long enough to show a person, not a «+» or an emoji."""
    return len((text or '').strip()) >= settings().probation.min_length


async def check(ctx, msg, user_id: int, name: str, say) -> bool:
    """True when the message was removed by probation."""
    group = getattr(msg, 'media_group_id', None)
    captioned = ctx.bot_data.setdefault('captioned_albums', {})
    if group and (getattr(msg, 'caption', None) or '').strip():
        if len(captioned) > 500:
            captioned.clear()
        captioned[group] = True       # only the first part of an album carries the words
    what = risky(msg)
    if what == 'a picture or video without words' and group in captioned:
        what = None
    if not what or not on_probation(user_id):
        return False
    try:
        await msg.delete()
    except Exception:
        return False
    told = ctx.bot_data.setdefault(TOLD, set())
    if len(told) > 5000:
        told.clear()
    if user_id not in told:
        told.add(user_id)
        await say(ctx, 'probation', user_id, name, msg)
    state.log_action('probation', user_id, name, f'{what} before {settings().probation.messages} messages',
                     msg.caption or '')
    return True


def profile_reason(bio: str, spam_words) -> str | None:
    reason = spam_reason(bio or '', [], spam_words, False)
    return f'{reason} in the profile' if reason else None


async def profile_problem(ctx, user_id: int) -> str | None:
    """Why this person's profile looks like an ad, or None. Asked once per person; any error = no problem."""
    if not settings().profile_check:
        return None
    cache = ctx.bot_data.setdefault('profiles', {})
    if len(cache) > 5000:
        cache.clear()
    if user_id not in cache:
        try:
            chat = await ctx.bot.get_chat(user_id)
            cache[user_id] = getattr(chat, 'bio', None) or ''
        except Exception as e:
            log.info('profile of %s not readable: %s', user_id, e)
            cache[user_id] = ''
    return profile_reason(cache[user_id], settings().spam_words)
