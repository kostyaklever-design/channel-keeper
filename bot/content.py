"""Where the channel's content comes from: a local folder or a private GitHub repository.

Content = posts.yaml, keeper.yaml and the images posts refer to. Keeping it in a
separate private repository means the bot's code can be public while the content
plan stays private, and editing a post does not redeploy the bot.
"""
import base64
import logging
import pathlib

import httpx

log = logging.getLogger('channel-keeper')
API = 'https://api.github.com'


class ContentError(Exception):
    """A file could not be read. The caller keeps using the last good copy."""


class ContentSource:
    def __init__(self, repo: str = '', token: str = '', branch: str = 'main', local_dir: str = '.'):
        self.repo = repo.strip().strip('/')
        self.token = token.strip()
        self.branch = branch.strip() or 'main'
        self.local_dir = pathlib.Path(local_dir)

    @property
    def remote(self) -> bool:
        return bool(self.repo)

    def describe(self) -> str:
        return f'github:{self.repo}@{self.branch}' if self.remote else f'local:{self.local_dir.resolve()}'

    async def read_bytes(self, path: str) -> bytes | None:
        """File contents, or None when the file does not exist. Raises ContentError on other failures."""
        path = path.lstrip('/')
        if '..' in pathlib.PurePosixPath(path).parts:
            raise ContentError(f'{path}: ".." is not allowed in content paths')
        if not self.remote:
            p = self.local_dir / path
            return p.read_bytes() if p.is_file() else None
        headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        url = f'{API}/repos/{self.repo}/contents/{path}'
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.get(url, params={'ref': self.branch}, headers=headers)
        except httpx.HTTPError as e:
            raise ContentError(f'{path}: {e}') from e
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            # 401/403: wrong token or no access to the repository.
            raise ContentError(f'{path}: GitHub answered {r.status_code}')
        body = r.json()
        if isinstance(body, list) or body.get('type') != 'file':
            raise ContentError(f'{path}: not a file')
        if body.get('encoding') == 'base64' and body.get('content') is not None:
            return base64.b64decode(body['content'])
        # Files over 1 MB come without content; fetch them raw.
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(url, params={'ref': self.branch},
                                 headers={**headers, 'Accept': 'application/vnd.github.raw'})
        if r.status_code != 200:
            raise ContentError(f'{path}: GitHub answered {r.status_code}')
        return r.content

    async def read_text(self, path: str) -> str | None:
        data = await self.read_bytes(path)
        return None if data is None else data.decode('utf-8')
