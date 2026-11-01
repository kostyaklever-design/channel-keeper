"""Tests import the running bot anew for every test, so each gets its own empty database.

Removing a module from sys.modules is not enough: `from . import guard` inside bot/main.py
returns the old module still stored on the `bot` package. Both places are cleared here."""
import importlib
import sys

import bot

# Modules that hold the running bot's memory (they create it on import from the environment).
RUNTIME = ('runtime', 'dm_posts', 'channel_queue', 'draft_flow', 'feeds', 'captcha', 'guard', 'setup', 'ai_flow',
           'report', 'review', 'probation', 'inbox', 'joins', 'language', 'main')


def drop() -> None:
    for name in RUNTIME:
        sys.modules.pop(f'bot.{name}', None)
        if hasattr(bot, name):
            delattr(bot, name)


def load(name: str):
    drop()
    return importlib.import_module(f'bot.{name}')
