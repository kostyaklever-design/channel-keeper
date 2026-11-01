"""The bot's command menu (the «Menu» button): command and its short description, in English;
language.py sets it in the owners' language at start. Pure data — tests read it without a bot."""
PRIVATE = [('setup', 'pick the channel and group, check rights'), ('queue', 'what goes out and when'),
           ('drafts', 'drafts waiting for you'), ('sources', 'feeds and their last check'),
           ('report', "the channel's week"), ('log', 'what the bot did'), ('ai', 'drafts from the AI; /ai key adds the key'),
           ('lang', 'language: /lang ru, /lang en, /lang auto'), ('forget', 'delete everything about a person'),
           ('id', 'chat id and your user id'), ('version', 'which version is running')]
IN_GROUP = [('ban', 'reply to a message to ban its author'), ('unban', 'lift a ban'), ('id', 'chat id and your user id')]
