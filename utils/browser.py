"""浏览器登录辅助函数"""

from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from utils.debug import debug_print, is_debug_enabled
from utils.popups import dismiss_popups, setup_popup_guard
from utils.proxy import get_playwright_proxy

if TYPE_CHECKING:
	from playwright.async_api import BrowserContext, Locator, Page

EMAIL_LOGIN_BUTTON_NAMES = (
	re.compile(r'邮箱或用户名'),
	re.compile(r'使用.*邮箱'),
	re.compile(r'Email or Username', re.I),
	re.compile(r'Sign in with Email', re.I),
	re.compile(r'Sign in with Email or Username', re.I),
)
EMAIL_LOGIN_ENTRY_SELECTORS = (
	'.semi-card button:has(.semi-icon-mail):not(form.semi-form button)',
	'.semi-card button:has([aria-label="mail"]):not(form.semi-form button)',
	'.semi-card button.semi-button-primary:has(.semi-icon-mail)',
	'button:has(.semi-icon-mail):not(form.semi-form button)',
)
LOGIN_PAGE_READY_SELECTORS = (
	'.semi-card button:has(.semi-icon-mail)',
	'.semi-card',
	'button:has(.semi-icon-mail)',
	'input[data-slot="form-control"]',
	'input[placeholder*="用户名"]',
	'input[placeholder*="电子邮件"]',
	'input[placeholder*="密码"]',
	'button[type="submit"]',
)
LOGIN_FORM_SELECTOR = 'form.semi-form'
USERNAME_SELECTORS = (
	'#username',
	'input[name="username"]',
	'input[name="email"]',
	'input[type="email"]',
	'input[placeholder*="用户名"]',
	'input[placeholder*="电子邮件"]',
	'input[placeholder*="邮箱"]',
	'input[placeholder*="email" i]',
	'input[placeholder*="username" i]',
	'input[data-slot="form-control"]:not([type="password"]):not([type="hidden"]):not([type="checkbox"])',
)
PASSWORD_SELECTORS = (
	'#password',
	'input[name="password"]',
	'input[type="password"]',
	'input[placeholder*="密码"]',
	'input[placeholder*="password" i]',
)  # nosec B105
SUBMIT_SELECTORS = (
	f'{LOGIN_FORM_SELECTOR} button[type="submit"]',
	'form button[type="submit"]',
	'button[type="submit"]',
)
SESSION_COOKIE_NAME = 'session'
SESSION_HINT_COOKIE_NAME = 'new_api_has_session'
USER_SELF_API_SUFFIX = '/api/user/self'
LOGIN_API_SUFFIX = '/api/user/login'
CONSOLE_PATH = '/console'
DASHBOARD_PATH = '/dashboard'
AUTH_STORAGE_KEY = 'new-api:auth-session'
DEFAULT_SCREENSHOT_DIR = 'checkin_screenshots'
DEFAULT_TIMEOUT_MS = 60_000
_pending_notify_screenshots: list[Path] = []
FORM_ACTION_TIMEOUT_MS = 15_000
EMAIL_TAB_TIMEOUT_MS = 8_000
WAF_READY_TIMEOUT_MS = 30_000
SESSION_WAIT_TIMEOUT_MS = 45_000

_VISIBLE_CHECK_JS = """
	const isVisible = (el) => {
		if (!el || !el.isConnected) return false;
		const style = window.getComputedStyle(el);
		if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
			return false;
		}
		const rect = el.getBoundingClientRect();
		return rect.width > 0 && rect.height > 0;
	};
	const countVisible = (selector) => [...document.querySelectorAll(selector)].filter(isVisible).length;
"""

_SITE_READY_JS = f"""() => {{
{_VISIBLE_CHECK_JS}
	const text = document.body?.innerText || '';
	const blocked = /请进行验证|为了更好的访问体验|访问受限|Access denied|verify you are human/i.test(text);
	if (blocked) return false;
	const wafBlockers = document.querySelector(
		'iframe[src*="captcha"], iframe[src*="verify"], iframe[src*="slide"], .nc-container, #nocaptcha'
	);
	if (wafBlockers) {{
		const rect = wafBlockers.getBoundingClientRect?.();
		if (rect && rect.width > 0 && rect.height > 0) return false;
	}}
	if (/\\/(login|sign-in|signin)/.test(location.pathname)) {{
		return countVisible('.semi-card') > 0 || countVisible('#username') > 0
			|| countVisible('input[data-slot="form-control"]') > 0
			|| countVisible('input[placeholder*="用户名"]') > 0
			|| countVisible('input[type="password"]') > 0
			|| countVisible('button') >= 2;
	}}
	return countVisible('a') > 0 || countVisible('button') > 0;
}}"""

_LOGIN_SHELL_READY_JS = f"""() => {{
{_VISIBLE_CHECK_JS}
	const text = document.body?.innerText || '';
	const blocked = /请进行验证|为了更好的访问体验|访问受限|Access denied|verify you are human/i.test(text);
	if (blocked) return false;
	return countVisible('.semi-card') > 0 || countVisible('#username') > 0
		|| countVisible('input[data-slot="form-control"]') > 0
		|| countVisible('input[placeholder*="用户名"]') > 0
		|| countVisible('input[type="password"]') > 0
		|| countVisible('button') >= 2;
}}"""

_OPEN_EMAIL_FORM_JS = """() => {
	const isVisible = (el) => {
		if (!el || !el.isConnected) return false;
		const style = window.getComputedStyle(el);
		if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
			return false;
		}
		const rect = el.getBoundingClientRect();
		return rect.width > 0 && rect.height > 0;
	};

	const inDialog = (el) => !!el?.closest('[role="dialog"][aria-modal="true"], .semi-modal-content[role="dialog"]');

	const usernameSelectors = ['#username', 'input[name="username"]', 'input[name="email"]', 'input[type="email"]', 'input[placeholder*="用户名"]', 'input[placeholder*="电子邮件"]', 'input[placeholder*="邮箱"]', 'input[data-slot="form-control"]:not([type="password"]):not([type="hidden"]):not([type="checkbox"])'];
	const findUsername = () => {
		for (const selector of usernameSelectors) {
			const el = document.querySelector(selector);
			if (isVisible(el)) return el;
		}
		return null;
	};

	if (findUsername()) return true;

	const entrySelectors = [
		'.semi-card button:has(.semi-icon-mail)',
		'.semi-card button:has([aria-label="mail"])',
	];
	for (const selector of entrySelectors) {
		for (const btn of document.querySelectorAll(selector)) {
			if (!isVisible(btn) || inDialog(btn) || btn.closest('form.semi-form')) continue;
			btn.click();
			if (findUsername()) return true;
		}
	}

	for (const tab of document.querySelectorAll('.semi-card .semi-tabs-tab')) {
		if (!isVisible(tab) || inDialog(tab)) continue;
		tab.click();
		if (findUsername()) return true;
	}

	return !!findUsername();
}"""


_READ_AUTH_SESSION_JS = """() => {
	const keys = ['new-api:auth-session', 'new-api:session', 'auth-session'];
	for (const key of keys) {
		try {
			const raw = localStorage.getItem(key) || sessionStorage.getItem(key);
			if (!raw) continue;
			const parsed = JSON.parse(raw);
			if (parsed && typeof parsed === 'object') return parsed;
			if (typeof parsed === 'string' && parsed) return {access_token: parsed};
		} catch (e) {}
	}
	return null;
}"""

_FETCH_USER_SELF_JS = """async () => {
	const readToken = () => {
		try {
			const raw = localStorage.getItem('new-api:auth-session')
				|| sessionStorage.getItem('new-api:auth-session');
			if (!raw) return null;
			const parsed = JSON.parse(raw);
			return parsed?.access_token || parsed?.accessToken || parsed?.data?.access_token || null;
		} catch (e) {
			return null;
		}
	};
	const token = readToken();
	const headers = {Accept: 'application/json'};
	if (token) headers['Authorization'] = 'Bearer ' + token;
	const res = await fetch('/api/user/self', {headers, credentials: 'include'});
	if (!res.ok) return null;
	return await res.json();
}"""

_MINT_TURNSTILE_JS = """async () => {
	const existing = document.querySelector('input[name="cf-turnstile-response"]')?.value;
	if (existing) return existing;

	const ensureTurnstile = async () => {
		if (window.turnstile?.render) return true;
		await new Promise((resolve, reject) => {
			const script = document.createElement('script');
			script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
			script.async = true;
			script.onload = () => resolve(true);
			script.onerror = () => reject(new Error('turnstile script'));
			document.head.appendChild(script);
		});
		const deadline = Date.now() + 8000;
		while (Date.now() < deadline) {
			if (window.turnstile?.render) return true;
			await new Promise((r) => setTimeout(r, 200));
		}
		return !!window.turnstile?.render;
	};

	const pickSiteKey = async () => {
		const el = document.querySelector('[data-sitekey], .cf-turnstile[data-sitekey]');
		if (el?.getAttribute('data-sitekey')) return el.getAttribute('data-sitekey');
		try {
			const res = await fetch('/api/status', {credentials: 'include'});
			const payload = await res.json();
			const data = payload?.data || payload || {};
			return data.turnstile_site_key || data.TurnstileSiteKey || data.turnstileSiteKey || null;
		} catch (e) {
			return null;
		}
	};

	const sitekey = await pickSiteKey();
	if (!sitekey) return null;
	try {
		if (!await ensureTurnstile()) return null;
	} catch (e) {
		return null;
	}

	return await new Promise((resolve) => {
		// 保留在视口内：Turnstile 对完全移出屏幕的宿主可能拒绝执行
		const host = document.createElement('div');
		host.style.position = 'fixed';
		host.style.bottom = '0';
		host.style.right = '0';
		host.style.width = '300px';
		host.style.height = '65px';
		host.style.opacity = '0.01';
		host.style.pointerEvents = 'none';
		host.style.zIndex = '2147483647';
		document.body.appendChild(host);

		let done = false;
		let widgetId = null;
		const finish = (token) => {
			if (done) return;
			done = true;
			try {
				if (widgetId !== null) window.turnstile.remove(widgetId);
			} catch (e) {}
			host.remove();
			resolve(token || null);
		};
		try {
			widgetId = window.turnstile.render(host, {
				sitekey,
				size: 'invisible',
				callback: (token) => finish(token),
				'error-callback': () => finish(null),
				'timeout-callback': () => finish(null),
			});
		} catch (e) {
			finish(null);
			return;
		}
		setTimeout(() => finish(null), 25000);
	});
}"""


@dataclass(frozen=True)
class BrowserLoginResult:
	cookies: dict[str, str]
	api_user: str | None = None
	access_token: str | None = None
	turnstile_token: str | None = None


@dataclass(frozen=True)
class VerifiedLogin:
	profile: dict | None = None
	access_token: str | None = None


class AuthCapture:
	"""拦截登录与用户信息接口，收集 access_token 和用户档案。"""

	def __init__(self, page: Page) -> None:
		self.page = page
		self.access_token: str | None = None
		self.user_profile: dict | None = None
		self._bound = False

	async def _on_response(self, response) -> None:
		try:
			url = response.url
			status = response.status
		except Exception:  # nosec B110
			return
		if status != 200:
			return
		if LOGIN_API_SUFFIX not in url and USER_SELF_API_SUFFIX not in url:
			return
		try:
			payload = await response.json()
		except Exception:  # nosec B110
			return
		if not isinstance(payload, dict):
			return
		token = extract_access_token(payload)
		if token:
			self.access_token = token
		profile = _extract_user_profile(payload)
		if profile:
			self.user_profile = profile

	def start(self) -> None:
		if self._bound:
			return
		self.page.on('response', self._on_response)
		self._bound = True

	def stop(self) -> None:
		if not self._bound:
			return
		try:
			self.page.remove_listener('response', self._on_response)
		except Exception:  # nosec B110
			pass
		self._bound = False

	async def snapshot_from_page(self) -> None:
		if not self.access_token:
			self.access_token = await read_stored_access_token(self.page)
		if not self.user_profile:
			self.user_profile = await fetch_user_self_from_page(self.page)
		if not self.user_profile:
			stored = None
			try:
				stored = await self.page.evaluate(_READ_AUTH_SESSION_JS)
			except Exception:  # nosec B110
				stored = None
			if isinstance(stored, dict):
				self.user_profile = _extract_user_profile({'success': True, 'data': stored}) or _extract_user_profile(
					stored
				)
				if not self.access_token:
					self.access_token = extract_access_token(stored) or extract_access_token({'data': stored})


@dataclass(frozen=True)
class BrowserLoginSettings:
	headless: bool
	humanize: bool
	wait_timeout_ms: int
	profile_dir: Path
	cloakbrowser_binary_path: str | None
	persist_profile: bool


def _env_bool(name: str, default: bool) -> bool:
	raw = os.getenv(name)
	if raw is None:
		return default
	return raw.strip().lower() in {'1', 'true', 'yes', 'on'}


def load_browser_login_settings(
	account_name: str, provider: str, *, persist_profile: bool = True
) -> BrowserLoginSettings:
	profile_base = Path(os.getenv('CHECKIN_BROWSER_PROFILE_DIR', '.browser_profiles'))
	profile_dir = profile_base / provider / account_name
	humanize = _env_bool('CHECKIN_HUMANIZE', True)
	if provider == 'agentrouter':
		humanize = _env_bool('CHECKIN_HUMANIZE_AGENTROUTER', humanize)
	return BrowserLoginSettings(
		headless=_env_bool('CHECKIN_HEADLESS', True),
		humanize=humanize,
		wait_timeout_ms=int(os.getenv('CHECKIN_WAIT_TIMEOUT_MS', str(DEFAULT_TIMEOUT_MS))),
		profile_dir=profile_dir,
		cloakbrowser_binary_path=os.getenv('CLOAKBROWSER_BINARY_PATH', '').strip() or None,
		persist_profile=persist_profile,
	)


def _ensure_binary_path(settings: BrowserLoginSettings) -> None:
	if settings.cloakbrowser_binary_path:
		os.environ['CLOAKBROWSER_BINARY_PATH'] = settings.cloakbrowser_binary_path


class _EphemeralBrowserContext:
	def __init__(self, context: BrowserContext, browser) -> None:
		self._context = context
		self._browser = browser

	def __getattr__(self, name: str):
		return getattr(self._context, name)

	async def close(self, *args, **kwargs) -> None:
		try:
			await self._context.close(*args, **kwargs)
		finally:
			await self._browser.close()


async def launch_login_context(settings: BrowserLoginSettings, *, use_proxy: bool = False) -> BrowserContext:
	_ensure_binary_path(settings)

	launch_kwargs: dict = {
		'headless': settings.headless,
		'humanize': settings.humanize,
		'viewport': {'width': 1920, 'height': 1080},
	}
	if settings.humanize:
		launch_kwargs['human_preset'] = 'careful'

	proxy = get_playwright_proxy(use_proxy=use_proxy)
	if proxy:
		launch_kwargs['proxy'] = proxy
		if is_debug_enabled():
			print(f'[INFO] Browser proxy enabled: {proxy["server"]}')
		else:
			print('[INFO] Browser proxy enabled')
	elif use_proxy:
		print('[WARN] Provider requires proxy but CHECKIN_PROXY_URL is not set')

	if settings.persist_profile:
		from cloakbrowser import launch_persistent_context_async

		settings.profile_dir.mkdir(parents=True, exist_ok=True)
		return await launch_persistent_context_async(str(settings.profile_dir), **launch_kwargs)

	from cloakbrowser import launch_async

	context_kwargs = {'viewport': launch_kwargs.pop('viewport')}
	browser = await launch_async(**launch_kwargs)
	context = await browser.new_context(**context_kwargs)
	return _EphemeralBrowserContext(context, browser)


def get_screenshot_dir() -> Path:
	return Path(os.getenv('CHECKIN_SCREENSHOT_DIR', DEFAULT_SCREENSHOT_DIR))


def _sanitize_screenshot_part(value: str) -> str:
	cleaned = re.sub(r'[^\w.-]+', '_', value.strip())
	return cleaned or 'unknown'


async def save_login_screenshot(
	page: Page,
	provider: str,
	account_name: str,
	label: str,
) -> Path | None:
	if not is_debug_enabled():
		return None

	screenshot_dir = get_screenshot_dir()
	screenshot_dir.mkdir(parents=True, exist_ok=True)
	timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
	filename = (
		f'{_sanitize_screenshot_part(provider)}_{_sanitize_screenshot_part(account_name)}'
		f'_{timestamp}_{_sanitize_screenshot_part(label)}.png'
	)
	path = screenshot_dir / filename
	try:
		await page.screenshot(path=str(path), full_page=True, timeout=15_000)
		_pending_notify_screenshots.append(path)
		print(f'[INFO] Screenshot saved: {path}')
		return path
	except Exception as exc:
		print(f'[WARN] Failed to save screenshot ({label}): {exc}')
		return None


def take_pending_screenshots() -> list[Path]:
	"""取出待推送的登录截图列表并清空缓存。"""
	paths = list(_pending_notify_screenshots)
	_pending_notify_screenshots.clear()
	return paths


async def prepare_browser_page(page: Page) -> None:
	await setup_popup_guard(page)


async def wait_for_site_ready(page: Page, timeout_ms: int = WAF_READY_TIMEOUT_MS) -> None:
	"""等待 WAF 通过并关闭弹窗。"""
	waf_timeout = min(timeout_ms, WAF_READY_TIMEOUT_MS)
	await page.wait_for_load_state('domcontentloaded', timeout=waf_timeout)
	try:
		await page.wait_for_function(_SITE_READY_JS, timeout=waf_timeout)
	except Exception:
		await asyncio.sleep(3)
	closed = await dismiss_popups(page)
	if closed:
		print(f'[INFO] Dismissed {closed} popup dialog(s)')


async def _wait_for_optional_load_state(page: Page, state: str, timeout_ms: int) -> bool:
	try:
		await page.wait_for_load_state(state, timeout=timeout_ms)
		return True
	except Exception as exc:  # nosec B110
		debug_print(f'[INFO] Optional load state "{state}" not reached within {timeout_ms}ms: {exc}')
		return False


async def _settle_page(page: Page, delay_seconds: float, networkidle_timeout_ms: int) -> None:
	await asyncio.sleep(delay_seconds)
	await _wait_for_optional_load_state(page, 'networkidle', networkidle_timeout_ms)


async def _wait_for_login_shell(page: Page, timeout_ms: int) -> bool:
	shell_timeout = min(timeout_ms, 60_000)
	try:
		await page.wait_for_function(_LOGIN_SHELL_READY_JS, timeout=shell_timeout)
		return True
	except Exception:  # nosec B110
		return False


async def navigate_login_page(
	page: Page,
	login_url: str,
	timeout_ms: int,
	*,
	provider: str = '',
	account_name: str = '',
) -> None:
	"""预热站点、导航登录页并等待 SPA 渲染完成。"""
	from urllib.parse import urlparse

	parsed = urlparse(login_url)
	base_url = f'{parsed.scheme}://{parsed.netloc}/'
	attempt_timeout = min(timeout_ms, 60_000)

	try:
		print(f'[INFO] Warming up {base_url} before login')
		await page.goto(base_url, wait_until='load', timeout=attempt_timeout)
		await _settle_page(page, 3, 15_000)
		closed = await dismiss_popups(page)
		if closed:
			print(f'[INFO] Dismissed {closed} popup dialog(s) during warmup')
	except Exception as exc:
		print(f'[WARN] Warmup navigation failed: {exc}')

	for attempt in range(3):
		print(f'[INFO] Navigating login page (attempt {attempt + 1}/3): {login_url}')
		await page.goto(login_url, wait_until='load', timeout=attempt_timeout)
		await _settle_page(page, 5, 20_000)

		if await _wait_for_login_shell(page, attempt_timeout):
			await wait_for_site_ready(page, timeout_ms)
			if await page.evaluate(_LOGIN_SHELL_READY_JS):
				return

		print(f'[WARN] Login page shell not ready on attempt {attempt + 1}')
		await _log_login_page_state(page)
		if provider and account_name:
			await save_login_screenshot(page, provider, account_name, f'login-shell-attempt-{attempt + 1}')
		if attempt < 2:
			await asyncio.sleep(5)
			try:
				await page.reload(wait_until='load', timeout=attempt_timeout)
			except Exception:  # nosec B110
				pass

	raise TimeoutError(f'Login page never rendered: {login_url}')


async def has_session_cookie(page: Page) -> bool:
	cookies = await page.context.cookies()
	names = {SESSION_COOKIE_NAME, SESSION_HINT_COOKIE_NAME}
	return any(c.get('name') in names and c.get('value') for c in cookies)


def extract_access_token(payload: object) -> str | None:
	"""从登录 JSON 或 localStorage 会话对象中取出 access_token。"""
	if not isinstance(payload, dict):
		return None
	candidates: list[object] = [payload.get('access_token'), payload.get('accessToken')]
	data = payload.get('data')
	if isinstance(data, dict):
		candidates.extend([data.get('access_token'), data.get('accessToken')])
		user = data.get('user')
		if isinstance(user, dict):
			candidates.append(user.get('access_token'))
	for token in candidates:
		if isinstance(token, str) and token.strip():
			return token.strip()
	return None


def _extract_user_profile(payload: object) -> dict | None:
	if not isinstance(payload, dict):
		return None
	data = payload.get('data')
	if isinstance(data, dict):
		user = data.get('user')
		if isinstance(user, dict) and user.get('id') is not None:
			return user
		if data.get('id') is not None:
			return data
	if payload.get('success') is True and isinstance(data, dict) and data.get('id'):
		return data
	if payload.get('id') is not None:
		return payload
	return None


async def read_stored_access_token(page: Page) -> str | None:
	try:
		stored = await page.evaluate(_READ_AUTH_SESSION_JS)
	except Exception:  # nosec B110
		return None
	if isinstance(stored, dict):
		return extract_access_token(stored) or extract_access_token({'data': stored})
	return None


async def fetch_user_self_from_page(page: Page) -> dict | None:
	try:
		payload = await page.evaluate(_FETCH_USER_SELF_JS)
	except Exception:  # nosec B110
		return None
	return _extract_user_profile(payload)


async def mint_turnstile_token(page: Page) -> str | None:
	"""登录会消耗一次 Turnstile token，签到前再在页面里领一枚新的。"""
	try:
		token = await page.evaluate(_MINT_TURNSTILE_JS)
	except Exception as exc:  # nosec B110
		debug_print(f'[WARN] Turnstile mint failed: {exc}')
		return None
	if isinstance(token, str) and token.strip():
		return token.strip()
	return None


async def _parse_user_self_response(response) -> dict | None:
	if USER_SELF_API_SUFFIX not in response.url or response.status != 200:
		return None
	try:
		payload = await response.json()
	except Exception:  # nosec B110
		return None
	return _extract_user_profile(payload)


def _url_path(url: str) -> str:
	"""只取 path，避免 /sign-in?redirect=/dashboard 这类查询串造成误判。"""
	from urllib.parse import urlparse

	try:
		return (urlparse(url).path or '/').lower()
	except Exception:  # nosec B110
		return url.lower()


async def is_logged_in(page: Page) -> bool:
	"""快速判断：是否已进入控制台/仪表盘，或仍停留在登录页。"""
	path = _url_path(page.url)
	if '/login' in path or '/signin' in path or '/sign-in' in path:
		return False
	if CONSOLE_PATH in path or DASHBOARD_PATH in path or path.rstrip('/').endswith('/profile'):
		return True

	try:
		if await page.locator('.semi-card button:has(.semi-icon-mail)').first.is_visible():
			return False
	except Exception:  # nosec B110
		pass
	return False


async def wait_for_session_cookie(page: Page, timeout_ms: int = SESSION_WAIT_TIMEOUT_MS) -> bool:
	deadline = time.monotonic() + timeout_ms / 1000
	while time.monotonic() < deadline:
		if await has_session_cookie(page):
			return True
		await asyncio.sleep(0.5)
	return False


async def wait_for_logged_in(page: Page, timeout_ms: int = SESSION_WAIT_TIMEOUT_MS) -> bool:
	deadline = time.monotonic() + timeout_ms / 1000
	while time.monotonic() < deadline:
		if await is_logged_in(page):
			return True
		await asyncio.sleep(0.5)
	return False


async def verify_browser_login(page: Page, console_url: str, timeout_ms: int) -> VerifiedLogin:
	"""跳转控制台/仪表盘并拦截用户信息，用浏览器会话确认登录。"""
	verify_timeout = min(timeout_ms, SESSION_WAIT_TIMEOUT_MS)
	captured_profile: dict | None = None
	captured_token: str | None = None
	verified = asyncio.Event()

	async def on_response(response) -> None:
		nonlocal captured_profile, captured_token
		try:
			if response.status != 200:
				return
			url = response.url
			if USER_SELF_API_SUFFIX not in url and LOGIN_API_SUFFIX not in url:
				return
			payload = await response.json()
		except Exception:  # nosec B110
			return
		token = extract_access_token(payload)
		if token:
			captured_token = token
		profile = _extract_user_profile(payload)
		if profile:
			captured_profile = profile
			verified.set()

	page.on('response', on_response)
	try:
		print(f'[INFO] Verifying login via {console_url} and {USER_SELF_API_SUFFIX}')
		await page.goto(console_url, wait_until='load', timeout=min(timeout_ms, 60_000))
		try:
			await page.wait_for_load_state('networkidle', timeout=20_000)
		except Exception:  # nosec B110
			pass

		if captured_profile is None:
			try:
				await asyncio.wait_for(verified.wait(), timeout=verify_timeout / 1000)
			except TimeoutError:
				pass

		if captured_token is None:
			captured_token = await read_stored_access_token(page)
		if captured_profile is None:
			captured_profile = await fetch_user_self_from_page(page)
		if captured_profile is None:
			try:
				stored = await page.evaluate(_READ_AUTH_SESSION_JS)
			except Exception:  # nosec B110
				stored = None
			if isinstance(stored, dict):
				captured_profile = _extract_user_profile({'success': True, 'data': stored}) or _extract_user_profile(
					stored
				)
				if captured_token is None:
					captured_token = extract_access_token(stored) or extract_access_token({'data': stored})
	finally:
		page.remove_listener('response', on_response)

	if captured_profile:
		if is_debug_enabled():
			user_id = captured_profile.get('id')
			username = captured_profile.get('username', '')
			print(f'[INFO] Login verified via {USER_SELF_API_SUFFIX}: id={user_id}, username={username}')
		else:
			print('[INFO] Login verified')
		return VerifiedLogin(profile=captured_profile, access_token=captured_token)

	if captured_token:
		print('[INFO] Login verified via access_token')
		return VerifiedLogin(profile=None, access_token=captured_token)

	url = page.url.lower()
	if CONSOLE_PATH in url or DASHBOARD_PATH in url:
		print(f'[WARN] Reached dashboard but {USER_SELF_API_SUFFIX} returned no user profile')
	else:
		debug_print(f'[WARN] Login verification failed: current URL={page.url}')
		print('[WARN] Login verification failed')
	return VerifiedLogin()


async def wait_for_waf_ready(page: Page, timeout_ms: int = WAF_READY_TIMEOUT_MS) -> None:
	await wait_for_site_ready(page, timeout_ms)


async def _first_visible_locator(page: Page, selectors: tuple[str, ...]) -> Locator | None:
	for selector in selectors:
		locator = page.locator(selector).first
		try:
			if await locator.is_visible():
				return locator
		except Exception:  # nosec B112
			continue
	return None


async def _is_email_form_visible(page: Page) -> bool:
	return await _first_visible_locator(page, USERNAME_SELECTORS) is not None


async def _dismiss_blocking_overlays(page: Page) -> None:
	if await _is_email_form_visible(page):
		return
	for _ in range(3):
		closed = await dismiss_popups(page)
		if closed == 0:
			break
		await asyncio.sleep(0.3)


async def _click_locator(button: Locator) -> bool:
	try:
		await button.scroll_into_view_if_needed()
		await button.click(timeout=FORM_ACTION_TIMEOUT_MS)
		return True
	except Exception:
		try:
			await button.click(force=True, timeout=FORM_ACTION_TIMEOUT_MS)
			return True
		except Exception:  # nosec B112
			return False


async def _wait_for_login_page_ready(page: Page, timeout_ms: int) -> None:
	if await _is_email_form_visible(page):
		return

	remaining_ms = timeout_ms
	for selector in LOGIN_PAGE_READY_SELECTORS:
		if remaining_ms <= 0:
			break
		try:
			await page.locator(selector).first.wait_for(state='visible', timeout=remaining_ms)
			return
		except Exception:  # nosec B112
			continue

	for pattern in EMAIL_LOGIN_BUTTON_NAMES:
		if remaining_ms <= 0:
			break
		try:
			await page.get_by_role('button', name=pattern).first.wait_for(state='visible', timeout=remaining_ms)
			return
		except Exception:  # nosec B112
			continue


async def _click_email_login_entry(page: Page) -> bool:
	for selector in EMAIL_LOGIN_ENTRY_SELECTORS:
		buttons = page.locator(selector)
		button_count = await buttons.count()
		for index in range(button_count):
			button = buttons.nth(index)
			try:
				if await button.is_visible():
					if await _click_locator(button):
						return True
			except Exception:  # nosec B112
				continue

	for pattern in EMAIL_LOGIN_BUTTON_NAMES:
		for scope in (page.locator('.semi-card'), page):
			try:
				button = scope.get_by_role('button', name=pattern).first
				if await button.is_visible() and await _click_locator(button):
					return True
			except Exception:  # nosec B112
				continue

	return False


async def _wait_for_username_input(page: Page, timeout_ms: int) -> bool:
	if timeout_ms <= 0:
		return await _is_email_form_visible(page)

	for selector in USERNAME_SELECTORS:
		try:
			await page.locator(selector).first.wait_for(state='visible', timeout=timeout_ms)
			return True
		except Exception:  # nosec B112
			continue
	return False


async def _log_login_page_state(page: Page) -> None:
	state = await page.evaluate(
		"""() => {
			const isVisible = (el) => {
				if (!el || !el.isConnected) return false;
				const style = window.getComputedStyle(el);
				if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) return false;
				const rect = el.getBoundingClientRect();
				return rect.width > 0 && rect.height > 0;
			};
			const buttons = [...document.querySelectorAll('button')]
				.filter(isVisible)
				.map((b) => (b.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 60));
			return {
				title: document.title || '',
				readyState: document.readyState,
				bodySnippet: (document.body?.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 300),
				scriptCount: document.querySelectorAll('script').length,
				hasSemiCard: !!document.querySelector('.semi-card'),
				mailEntryCount: document.querySelectorAll('.semi-card button:has(.semi-icon-mail)').length,
				usernameVisible: isVisible(document.querySelector('#username'))
					|| [...document.querySelectorAll('input[data-slot="form-control"], input[placeholder*="用户名"]')].some(isVisible),
				passwordVisible: [...document.querySelectorAll('input[type="password"], input[placeholder*="密码"]')].some(isVisible),
				turnstile: document.querySelectorAll('.cf-turnstile, iframe[src*="challenges.cloudflare.com"]').length,
				modalVisible: [...document.querySelectorAll('div[role="dialog"][aria-modal="true"]')].some(isVisible),
				buttons: buttons.slice(0, 8),
			};
		}"""
	)
	debug_print(f'[INFO] Login page state: {state}')


async def _open_email_login_form(
	page: Page,
	timeout_ms: int,
	*,
	provider: str = '',
	account_name: str = '',
) -> None:
	deadline = time.monotonic() + timeout_ms / 1000

	await _dismiss_blocking_overlays(page)
	if await _is_email_form_visible(page):
		return

	ready_timeout = min(timeout_ms, WAF_READY_TIMEOUT_MS)
	try:
		await _wait_for_login_page_ready(page, ready_timeout)
	except Exception:  # nosec B110
		pass

	while time.monotonic() < deadline:
		remaining_ms = int((deadline - time.monotonic()) * 1000)
		if remaining_ms <= 0:
			break

		await _dismiss_blocking_overlays(page)
		if await _is_email_form_visible(page):
			return

		if await _click_email_login_entry(page):
			await asyncio.sleep(1)
			wait_ms = min(remaining_ms, FORM_ACTION_TIMEOUT_MS)
			if await _wait_for_username_input(page, wait_ms):
				return

		tabs = page.locator('.semi-card .semi-tabs-tab')
		tab_count = await tabs.count()
		for index in range(tab_count):
			tab = tabs.nth(index)
			if not await tab.is_visible():
				continue
			await tab.click(timeout=EMAIL_TAB_TIMEOUT_MS)
			wait_ms = min(int((deadline - time.monotonic()) * 1000), EMAIL_TAB_TIMEOUT_MS)
			if await _wait_for_username_input(page, wait_ms):
				return

		if await page.evaluate(_OPEN_EMAIL_FORM_JS):
			await asyncio.sleep(1)
			wait_ms = min(int((deadline - time.monotonic()) * 1000), FORM_ACTION_TIMEOUT_MS)
			if await _wait_for_username_input(page, wait_ms):
				return

		await asyncio.sleep(0.5)

	remaining_ms = int((deadline - time.monotonic()) * 1000)
	if remaining_ms > 0 and await _wait_for_username_input(page, remaining_ms):
		return

	debug_print(f'[INFO] Login page URL: {page.url}')
	await _log_login_page_state(page)
	if provider and account_name:
		await save_login_screenshot(page, provider, account_name, 'email-form-timeout')
	raise TimeoutError(f'Cannot open email login form, selectors: {USERNAME_SELECTORS}')


async def _set_input_value(locator: Locator, value: str, timeout_ms: int) -> None:
	click_timeout = min(timeout_ms, 5000)
	try:
		await locator.click(timeout=click_timeout)
	except Exception:
		try:
			await locator.click(force=True, timeout=click_timeout)
		except Exception:  # nosec B110
			pass

	try:
		await locator.fill(value, timeout=timeout_ms)
		if await locator.input_value(timeout=2000) == value:
			return
	except Exception:  # nosec B110
		pass

	await locator.evaluate(
		"""(el, v) => {
			const setter = Object.getOwnPropertyDescriptor(
				window.HTMLInputElement.prototype, 'value'
			)?.set;
			setter?.call(el, v);
			el.dispatchEvent(new Event('input', { bubbles: true }));
			el.dispatchEvent(new Event('change', { bubbles: true }));
		}""",
		value,
	)


async def fill_email_credentials(page: Page, email: str, password: str, timeout_ms: int) -> None:
	await _dismiss_blocking_overlays(page)
	action_timeout = min(timeout_ms, FORM_ACTION_TIMEOUT_MS)

	username_input = await _first_visible_locator(page, USERNAME_SELECTORS)
	if not username_input:
		for selector in USERNAME_SELECTORS:
			locator = page.locator(selector).first
			try:
				await locator.wait_for(state='visible', timeout=action_timeout)
				username_input = locator
				break
			except Exception:  # nosec B112
				continue
	if not username_input:
		raise TimeoutError(f'Cannot find username input: {USERNAME_SELECTORS}')

	password_input = await _first_visible_locator(page, PASSWORD_SELECTORS)
	if not password_input:
		for selector in PASSWORD_SELECTORS:
			locator = page.locator(selector).first
			try:
				await locator.wait_for(state='visible', timeout=action_timeout)
				password_input = locator
				break
			except Exception:  # nosec B112
				continue
	if not password_input:
		raise TimeoutError(f'Cannot find password input: {PASSWORD_SELECTORS}')

	await _set_input_value(username_input, email, action_timeout)
	await _set_input_value(password_input, password, action_timeout)


async def _accept_legal_consent(page: Page) -> None:
	"""勾选登录页隐藏的服务条款复选框，避免提交按钮一直禁用。"""
	selectors = (
		'form input[type="checkbox"]',
		'input[type="checkbox"]',
		'button[role="checkbox"]',
		'[data-slot="checkbox"]',
	)
	for selector in selectors:
		try:
			locators = page.locator(selector)
			count = await locators.count()
		except Exception:  # nosec B112
			continue
		for index in range(count):
			box = locators.nth(index)
			try:
				checked = await box.is_checked()
			except Exception:  # nosec B110
				checked = False
			if checked:
				continue
			try:
				if await box.is_visible():
					await box.click(timeout=2000)
					continue
			except Exception:  # nosec B110
				pass
			try:
				await box.evaluate(
					"""(el) => {
						if (el instanceof HTMLInputElement) {
							el.checked = true;
							el.dispatchEvent(new Event('input', {bubbles: true}));
							el.dispatchEvent(new Event('change', {bubbles: true}));
						} else {
							el.click();
						}
					}"""
				)
			except Exception:  # nosec B112
				continue


async def submit_login_form(page: Page, timeout_ms: int) -> None:
	action_timeout = min(timeout_ms, FORM_ACTION_TIMEOUT_MS)
	submit = await _first_visible_locator(page, SUBMIT_SELECTORS)
	if not submit:
		for selector in SUBMIT_SELECTORS:
			locator = page.locator(selector).first
			try:
				await locator.wait_for(state='visible', timeout=action_timeout)
				submit = locator
				break
			except Exception:  # nosec B112
				continue
	if not submit:
		raise TimeoutError(f'Cannot find submit button: {SUBMIT_SELECTORS}')

	await _accept_legal_consent(page)

	wait_deadline = time.monotonic() + min(timeout_ms, 45_000) / 1000
	while time.monotonic() < wait_deadline:
		try:
			if not await submit.is_disabled():
				break
		except Exception:  # nosec B110
			break
		await asyncio.sleep(0.5)

	try:
		await submit.click(timeout=action_timeout)
	except Exception:
		await submit.click(force=True, timeout=action_timeout)
	await _wait_for_optional_load_state(page, 'domcontentloaded', action_timeout)
	await _wait_for_optional_load_state(page, 'networkidle', min(timeout_ms, 30_000))
	await wait_for_logged_in(page, SESSION_WAIT_TIMEOUT_MS)


async def login_with_email_form(
	page: Page,
	email: str,
	password: str,
	timeout_ms: int,
	*,
	provider: str = '',
	account_name: str = '',
) -> None:
	await _open_email_login_form(
		page,
		timeout_ms,
		provider=provider,
		account_name=account_name,
	)
	await fill_email_credentials(page, email, password, timeout_ms)
	await submit_login_form(page, timeout_ms)
