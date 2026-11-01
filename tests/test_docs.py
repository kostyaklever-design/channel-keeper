"""Guards: code, docs and secrets must not drift apart.
If one of these fails on GitHub, fix docs/ (or the code) in the same delivery."""
import pathlib
import re

ROOT = pathlib.Path(__file__).parent.parent
read = lambda p: (ROOT / p).read_text(encoding='utf-8')

# Content files belong to whoever runs the bot and may name their brand.
CONTENT_FILES = {'posts.yaml', 'keeper.yaml', 'sources.yaml'}
SKIP_DIRS = {'.git', '.pytest_cache', '__pycache__', 'posts', '.venv', 'venv'}
TEXT_SUFFIXES = {'.py', '.md', '.yaml', '.yml', '.json', '.txt', '.ini', '.toml', '.cfg', '.sh', ''}


def repo_files():
    for p in ROOT.rglob('*'):
        if p.is_file() and not (set(p.relative_to(ROOT).parts) & SKIP_DIRS) and p.suffix in TEXT_SUFFIXES:
            yield p


def code_commands() -> set[str]:
    return set(re.findall(r"CommandHandler\('(\w+)'", read('bot/main.py')))


def doc_commands() -> set[str]:
    return set(re.findall(r'^## /(\w+)', read('docs/COMMANDS.md'), re.M))


def code_env_vars() -> set[str]:
    # Every quoted UPPER_CASE name in config.py is an environment variable.
    return set(re.findall(r"'([A-Z][A-Z_]{2,})'", read('bot/config.py')))


def doc_env_vars() -> set[str]:
    return set(re.findall(r'^\| `([A-Z_]+)`', read('docs/CONFIG.md'), re.M))


def test_every_command_is_documented():
    missing = code_commands() - doc_commands()
    assert not missing, f'commands without docs in docs/COMMANDS.md: {sorted(missing)}'


def test_no_documented_command_is_gone():
    stale = doc_commands() - code_commands()
    assert not stale, f'docs/COMMANDS.md describes commands the bot no longer has: {sorted(stale)}'


def test_every_env_var_is_documented():
    missing = code_env_vars() - doc_env_vars()
    assert not missing, f'variables without docs in docs/CONFIG.md: {sorted(missing)}'


def test_no_documented_env_var_is_gone():
    stale = doc_env_vars() - code_env_vars()
    assert not stale, f'docs/CONFIG.md describes variables the bot no longer reads: {sorted(stale)}'


def test_version_matches_changelog():
    version = read('VERSION').strip()
    assert re.fullmatch(r'\d+\.\d+\.\d+', version), f'VERSION must look like 1.2.3, got {version!r}'
    top = re.search(r'^## \[(\d+\.\d+\.\d+)\]', read('CHANGELOG.md'), re.M)
    assert top, 'CHANGELOG.md has no "## [x.y.z]" entry'
    assert top.group(1) == version, f'VERSION is {version}, newest CHANGELOG entry is {top.group(1)}'


PAGES = ['README.md', 'README.ru.md'] + sorted(str(p.relative_to(ROOT)) for p in (ROOT / 'docs').glob('*.md'))


def test_every_doc_has_both_languages():
    """2.0.2: the documentation is complete in English and Russian — each page has its pair, with as many sections."""
    docs = ROOT / 'docs'
    english = sorted(p for p in docs.glob('*.md') if not p.name.endswith('.ru.md'))
    assert len(english) >= 10
    for page in english:
        ru = page.with_name(page.stem + '.ru.md')
        assert ru.exists(), f'{page.name} has no Russian version {ru.name}'
        count = lambda p: len(re.findall(r'^#{1,3} ', p.read_text(encoding='utf-8'), re.M))
        assert count(page) == count(ru), f'{page.name} and {ru.name} have different sections'
        assert f'({ru.name})' in page.read_text(encoding='utf-8') and f'({page.name})' in ru.read_text(encoding='utf-8')


def test_readme_links_exist():
    for readme in PAGES:
        base = (ROOT / readme).parent
        for target in re.findall(r'\]\((?!https?://)([^)#]+)\)', read(readme)):
            assert (base / target).exists(), f'{readme} links to a missing file: {target}'
        for src in re.findall(r'<img src="([^"]+)"', read(readme)):
            assert (base / src).exists(), f'{readme} shows a missing picture: {src}'


def anchors(path: str) -> set[str]:
    """GitHub's ids of the headings: lower case, punctuation dropped, spaces -> hyphens."""
    return {re.sub(r'[^\w\- ]', '', h.strip().lower()).replace(' ', '-')
            for h in re.findall(r'^#+ (.+)$', read(path), re.M)}


def test_readme_anchors_exist():
    """A link to a heading that was renamed opens the page at the top: the reader is lost."""
    for readme in PAGES:
        base = (ROOT / readme).parent
        for target, anchor in re.findall(r'\]\((?!https?://)([^)#]*)#([^)]+)\)', read(readme)):
            page = str(((base / target) if target else (ROOT / readme)).resolve().relative_to(ROOT.resolve()))
            assert anchor in anchors(page), f'{readme}: no heading #{anchor} in {page}'


def test_public_examples_are_valid():
    """examples/ is what strangers copy: it must load like the real files."""
    from bot.settings import parse_settings
    from bot.sources import parse_sources
    assert parse_settings(read('examples/keeper.ru.yaml')).rules.quiet is not None
    assert parse_sources(read('examples/sources.ru.yaml'))


def test_no_brand_in_code_or_docs():
    """The bot works for any channel: no hard-coded brand outside README, CHANGELOG and content files."""
    allowed = {'README.md', 'README.ru.md', 'CHANGELOG.md', 'LICENSE'} | CONTENT_FILES
    found = [str(p.relative_to(ROOT)) for p in repo_files()
             if p.name not in allowed and p.name != 'test_docs.py' and 'voxynx' in p.read_text(encoding='utf-8', errors='ignore').lower()]
    assert not found, f'brand name in code/docs (use settings instead): {found}'


TOKEN_PATTERNS = {
    'Telegram bot token': re.compile(r'\b\d{8,10}:[A-Za-z0-9_-]{35}\b'),
    'GitHub token': re.compile(r'\b(ghp|gho|ghs|ghu)_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{50,}\b'),
    'OpenAI key': re.compile(r'\bsk-[A-Za-z0-9_-]{30,}\b'),
}


def test_no_secrets_in_files():
    """Secrets live only in Railway variables, never in the repository."""
    hits = []
    for p in repo_files():
        text = p.read_text(encoding='utf-8', errors='ignore')
        hits += [f'{p.relative_to(ROOT)}: {kind}' for kind, rx in TOKEN_PATTERNS.items() if rx.search(text)]
    assert not hits, f'secret-looking strings found — move them to Railway variables: {hits}'


def logged_kinds() -> set[str]:
    kinds = set()
    for p in (ROOT / 'bot').glob('*.py'):
        kinds |= set(re.findall(r"log_action\(\s*'(\w+)'", p.read_text(encoding='utf-8')))
    kinds |= set(re.findall(r"'(warn|ban)'", read('bot/main.py')))   # main.py logs these through a variable
    return kinds


def test_every_logged_action_has_a_title():
    """/log shows TITLES[kind]; a new kind without a title would show a raw word like «queue_forced»."""
    from bot.notify import TITLES
    missing = logged_kinds() - set(TITLES)
    assert not missing, f'add these to TITLES in bot/notify.py: {sorted(missing)}'


PACKAGE_OF = {'telegram': 'python-telegram-bot', 'yaml': 'PyYAML'}


def imported_libraries() -> set[str]:
    import sys
    found = set()
    for p in (ROOT / 'bot').glob('*.py'):
        for mod in re.findall(r'^(?:from|import) ([a-zA-Z_]\w*)', p.read_text(encoding='utf-8'), re.M):
            if mod not in sys.stdlib_module_names:
                found.add(mod)
    return found


def test_every_library_is_in_requirements():
    """A library used in the code but missing from requirements.txt works on your computer and crashes on Railway."""
    req = {re.split(r'[\[=<> ]', line.strip(), maxsplit=1)[0].lower()
           for line in read('requirements.txt').splitlines() if line.strip() and not line.startswith('#')}
    missing = {m for m in imported_libraries() if PACKAGE_OF.get(m, m).lower() not in req}
    assert not missing, f'add to requirements.txt: {sorted(missing)}'


def test_guards_see_the_code():
    """Protects the guards themselves: if a regex stops matching, they would pass on nothing."""
    assert {'ban', 'unban', 'id', 'version', 'log', 'drafts', 'sources', 'queue'} <= code_commands()
    assert {'post', 'feed_new', 'queue_forced', 'captcha_kicked', 'warn', 'ban'} <= logged_kinds()
    assert {'feedparser', 'httpx', 'yaml', 'telegram'} <= imported_libraries()
    assert {'BOT_TOKEN', 'CHANNEL_ID', 'GROUP_ID', 'ADMIN_IDS', 'DATA_DIR', 'CONTENT_REPO'} <= code_env_vars()
    assert TOKEN_PATTERNS['Telegram bot token'].search('123456789:' + 'A' * 35)
    assert any(p.name == 'main.py' for p in repo_files())


def test_railway_keeps_its_own_builder():
    """1.1.1 broke the Railway build: seeing a Dockerfile, Railway switched to Docker and rejected VOLUME.
    railway.json pins Railway's builder, and the Dockerfile has no VOLUME, in case someone builds it there."""
    import json
    assert json.loads(read('railway.json'))['build']['builder'] == 'RAILPACK'
    assert not re.search(r'^\s*VOLUME', read('Dockerfile'), re.M)
    # 1.8.1 crashed on Railway: a non-root USER cannot write Railway's root-owned volume.
    assert not re.search(r'^\s*USER\b', read('Dockerfile'), re.M)


def test_line_endings_are_lf():
    """All text files use LF; .gitattributes keeps it so on every computer that checks the code out."""
    crlf = [str(p.relative_to(ROOT)) for p in repo_files() if b'\r\n' in p.read_bytes()]
    assert not crlf, f'CRLF line endings in: {crlf}'
    assert '* text=auto eol=lf' in read('.gitattributes')
