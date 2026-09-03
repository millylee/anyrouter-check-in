import sys
from types import SimpleNamespace

import pytest

from utils.browser import launch_login_context, load_browser_login_settings, navigate_login_page


def test_browser_login_settings_records_profile_persistence(monkeypatch, tmp_path):
	monkeypatch.setenv('CHECKIN_BROWSER_PROFILE_DIR', str(tmp_path))

	settings = load_browser_login_settings('Account 1', 'agentrouter', persist_profile=False)

	assert settings.persist_profile is False
	assert settings.profile_dir == tmp_path / 'agentrouter' / 'Account 1'


@pytest.mark.asyncio
async def test_launch_login_context_uses_persistent_context_when_enabled(monkeypatch, tmp_path):
	calls = {}
	context = SimpleNamespace()

	async def fake_launch_persistent_context_async(profile_dir, **kwargs):
		calls['profile_dir'] = profile_dir
		calls['kwargs'] = kwargs
		return context

	monkeypatch.setitem(
		sys.modules,
		'cloakbrowser',
		SimpleNamespace(launch_persistent_context_async=fake_launch_persistent_context_async),
	)

	settings = load_browser_login_settings('Account 1', 'anyrouter', persist_profile=True)
	settings = settings.__class__(
		headless=settings.headless,
		humanize=False,
		wait_timeout_ms=settings.wait_timeout_ms,
		profile_dir=tmp_path / 'profiles' / 'anyrouter' / 'Account 1',
		cloakbrowser_binary_path=settings.cloakbrowser_binary_path,
		persist_profile=settings.persist_profile,
	)

	result = await launch_login_context(settings)

	assert result is context
	assert calls['profile_dir'] == str(settings.profile_dir)


@pytest.mark.asyncio
async def test_launch_login_context_closes_browser_for_ephemeral_context(monkeypatch, tmp_path):
	class FakeContext:
		def __init__(self):
			self.closed = False

		async def close(self):
			self.closed = True

	class FakeBrowser:
		def __init__(self):
			self.context = FakeContext()
			self.closed = False
			self.context_kwargs = {}
			self.launch_kwargs = {}

		async def new_context(self, **kwargs):
			self.context_kwargs = kwargs
			return self.context

		async def close(self):
			self.closed = True

	browser = FakeBrowser()

	async def fake_launch_async(**kwargs):
		browser.launch_kwargs = kwargs
		return browser

	monkeypatch.setitem(
		sys.modules,
		'cloakbrowser',
		SimpleNamespace(launch_async=fake_launch_async),
	)

	settings = load_browser_login_settings('Account 1', 'agentrouter', persist_profile=False)
	settings = settings.__class__(
		headless=settings.headless,
		humanize=False,
		wait_timeout_ms=settings.wait_timeout_ms,
		profile_dir=tmp_path / 'profiles' / 'agentrouter' / 'Account 1',
		cloakbrowser_binary_path=settings.cloakbrowser_binary_path,
		persist_profile=settings.persist_profile,
	)

	context = await launch_login_context(settings)
	await context.close()

	assert context.closed is True
	assert browser.closed is True
	assert not settings.profile_dir.exists()


@pytest.mark.asyncio
async def test_navigate_login_page_retries_after_navigation_error(monkeypatch):
	class FakePage:
		def __init__(self):
			self.login_goto_calls = 0
			self.goto_calls = []

		async def goto(self, url, **kwargs):
			self.goto_calls.append((url, kwargs))
			if url.endswith('/login'):
				self.login_goto_calls += 1
				if self.login_goto_calls == 1:
					raise RuntimeError('net::ERR_NAME_NOT_RESOLVED')

		async def evaluate(self, _script):
			return True

	page = FakePage()

	async def _noop(*_args, **_kwargs):
		return None

	async def _zero(*_args, **_kwargs):
		return 0

	async def _true(*_args, **_kwargs):
		return True

	monkeypatch.setattr('utils.browser._settle_page', _noop)
	monkeypatch.setattr('utils.browser.dismiss_popups', _zero)
	monkeypatch.setattr('utils.browser._wait_for_login_shell', _true)
	monkeypatch.setattr('utils.browser.wait_for_site_ready', _noop)
	monkeypatch.setattr('utils.browser.asyncio.sleep', _noop)

	await navigate_login_page(page, 'https://anyrouter.top/login', 60_000)

	assert page.login_goto_calls == 2


@pytest.mark.asyncio
async def test_navigate_login_page_raises_after_retry_exhausted(monkeypatch):
	class FakePage:
		def __init__(self):
			self.login_goto_calls = 0

		async def goto(self, url, **kwargs):
			if url.endswith('/login'):
				self.login_goto_calls += 1
				raise RuntimeError('net::ERR_NAME_NOT_RESOLVED')

		async def evaluate(self, _script):
			return True

	page = FakePage()

	async def _noop(*_args, **_kwargs):
		return None

	async def _zero(*_args, **_kwargs):
		return 0

	monkeypatch.setattr('utils.browser._settle_page', _noop)
	monkeypatch.setattr('utils.browser.dismiss_popups', _zero)
	monkeypatch.setattr('utils.browser.asyncio.sleep', _noop)

	with pytest.raises(RuntimeError, match='ERR_NAME_NOT_RESOLVED'):
		await navigate_login_page(page, 'https://anyrouter.top/login', 60_000)

	assert page.login_goto_calls == 3
