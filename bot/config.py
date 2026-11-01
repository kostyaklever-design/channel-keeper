"""Secrets and wiring from environment variables (Railway -> Variables).

Only BOT_TOKEN is required. The channel, the group and the owners can come from here,
or be chosen in Telegram with /setup — then they are kept in the bot's memory.
Everything that is not a secret or a chat id lives in keeper.yaml instead.
"""
import os
from dataclasses import dataclass


def _ids(raw: str) -> set[int]:
    try:
        return {int(x) for x in raw.replace(' ', '').split(',') if x}
    except ValueError as e:
        raise SystemExit(f'ADMIN_IDS must be numbers separated by commas, got: {raw!r}') from e


def _int(name: str) -> int | None:
    raw = os.getenv(name, '').strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as e:
        raise SystemExit(f'{name} must be a number like -1001234567890, got: {raw!r}') from e


@dataclass
class Config:
    # Not frozen: /setup fills channel_id, group_id and admin_ids while the bot runs.
    bot_token: str
    channel_id: int | None       # the channel, e.g. -1001234567890; None until /setup
    group_id: int | None         # its discussion group; None until /setup
    admin_ids: set[int]          # owners: Telegram user ids allowed to manage the bot
    data_dir: str = '/data'      # persistent disk (Railway volume)
    content_repo: str = ''       # owner/name of a private GitHub repo with posts; empty = local files
    content_token: str = ''      # read-only GitHub token for that repo
    content_branch: str = 'main'
    content_dir: str = '.'       # local folder with posts.yaml / keeper.yaml when content_repo is empty

    @staticmethod
    def from_env() -> 'Config':
        if not os.getenv('BOT_TOKEN', '').strip():
            raise SystemExit('Missing environment variable BOT_TOKEN — the token from @BotFather')
        repo = os.getenv('CONTENT_REPO', '').strip()
        token = os.getenv('CONTENT_TOKEN', '').strip()
        if repo and repo.count('/') != 1:
            raise SystemExit(f'CONTENT_REPO must look like owner/name, got: {repo!r}')
        return Config(
            bot_token=os.environ['BOT_TOKEN'].strip(),
            channel_id=_int('CHANNEL_ID'),
            group_id=_int('GROUP_ID'),
            admin_ids=_ids(os.getenv('ADMIN_IDS', '')),
            data_dir=os.getenv('DATA_DIR', '/data'),
            content_repo=repo,
            content_token=token,
            content_branch=os.getenv('CONTENT_BRANCH', 'main'),
            content_dir=os.getenv('CONTENT_DIR', '.'),
        )


# The AI is optional (1.1): without AI_API_KEY the bot works exactly as before.
AI_DEFAULT_MODEL = {'anthropic': 'claude-haiku-5-5', 'openai': 'gpt-5-nano'}   # the cheapest of each, late 2026


def provider_of(key: str) -> str:
    """Anthropic keys start with sk-ant-, OpenAI keys with sk- (sk-proj-, sk-svcacct-, …)."""
    return 'anthropic' if key.startswith('sk-ant-') else 'openai'


@dataclass
class AIConfig:
    provider: str = ''
    key: str = ''
    model: str = ''
    monthly_limit: int = 300          # requests per calendar month; protects the owner's bill
    custom_model: str = ''            # AI_MODEL as set; empty = the cheapest model of the key's provider

    @property
    def on(self) -> bool:
        return bool(self.key)

    def with_key(self, key: str) -> 'AIConfig':
        """The same limits with a key added in Telegram (/setup): the provider is told by the key."""
        provider = provider_of(key)
        return AIConfig(provider, key, self.custom_model or AI_DEFAULT_MODEL[provider], self.monthly_limit,
                        self.custom_model)

    @staticmethod
    def from_env() -> 'AIConfig':
        key = os.getenv('AI_API_KEY', '').strip().strip('"\'').strip()     # quotes pasted with the key
        asked = os.getenv('AI_PROVIDER', '').strip().lower()
        if key and asked and asked not in AI_DEFAULT_MODEL:
            raise SystemExit(f'AI_PROVIDER must be anthropic or openai, got: {asked!r}')
        provider = asked or (provider_of(key) if key else 'anthropic')     # empty -> told by the key
        if key and asked and key.startswith('sk-') and provider_of(key) != asked:
            raise SystemExit(f'AI_API_KEY looks like a {provider_of(key)} key, but AI_PROVIDER is {asked!r}. '
                             f'Delete AI_PROVIDER (the bot tells by the key) or set it to {provider_of(key)!r}.')
        custom = os.getenv('AI_MODEL', '').strip()
        model = custom or AI_DEFAULT_MODEL[provider]
        raw = os.getenv('AI_MONTHLY_LIMIT', '300').strip() or '300'
        if not raw.isdigit() or not 1 <= int(raw) <= 100000:
            raise SystemExit(f'AI_MONTHLY_LIMIT must be a whole number of requests per month, got: {raw!r}')
        return AIConfig(provider, key, model, int(raw), custom)
