"""弹窗自动关闭：注入 JS 动态发现模态框特征并处理"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from playwright.async_api import Page

_MODAL_SELECTOR = 'div[role="dialog"][aria-modal="true"]'
_CLOSE_ANNOUNCEMENT = re.compile(r'关闭公告|Close Notice', re.I)
_DISMISS_TODAY = re.compile(r'今日关闭|Close Today', re.I)

_DISMISS_MODALS_CORE_JS = """
	const isVisible = (el) => {
		if (!el || !el.isConnected) return false;
		const style = window.getComputedStyle(el);
		if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) {
			return false;
		}
		const rect = el.getBoundingClientRect();
		return rect.width > 0 && rect.height > 0;
	};

	const modalSelectors = [
		'div[role="dialog"][aria-modal="true"]',
		'div.semi-modal .semi-modal-content[role="dialog"]',
		'div.semi-modal.semi-modal-large',
		'div.semi-modal[role="dialog"]',
		'div.semi-modal[aria-modal="true"]',
		'div.semi-modal-wrap',
	];

	const closeSelectors = [
		'button.semi-modal-close',
		'button[aria-label="close"]',
		'button[aria-label="Close"]',
		'.semi-modal-header button',
		'.semi-modal-footer button.semi-button-primary',
		'.semi-modal-footer button:last-child',
		'.semi-modal-footer button',
	];

	const findRoots = () => {
		const roots = [document.body, document.documentElement];
		for (const portal of document.querySelectorAll('div.semi-portal')) {
			roots.push(portal);
		}
		return roots;
	};

	const findModals = () => {
		const seen = new Set();
		const modals = [];
		for (const root of findRoots()) {
			if (!root) continue;
			for (const selector of modalSelectors) {
				for (const el of root.querySelectorAll(selector)) {
					if (isVisible(el) && !seen.has(el)) {
						seen.add(el);
						modals.push(el);
					}
				}
			}
		}
		return modals.sort((a, b) => {
			const za = parseInt(window.getComputedStyle(a).zIndex, 10) || 0;
			const zb = parseInt(window.getComputedStyle(b).zIndex, 10) || 0;
			return zb - za;
		});
	};

	const loginFieldSelectors = [
		'form.semi-form',
		'#username',
		'input[name="username"]',
		'input[name="email"]',
		'input[type="email"]',
		'input[type="password"]',
		'#password',
	];

	const hasLoginFields = (root) => {
		if (!root) return false;
		for (const selector of loginFieldSelectors) {
			const el = root.querySelector(selector);
			if (el && isVisible(el)) return true;
		}
		return false;
	};

	const findCloseButton = (modal) => {
		for (const selector of closeSelectors) {
			const btn = modal.querySelector(selector);
			if (btn && isVisible(btn)) return btn;
		}
		return null;
	};

	const dismissPortalButtons = () => {
		let closed = 0;
		for (const portal of document.querySelectorAll('div.semi-portal')) {
			if (!isVisible(portal) || hasLoginFields(portal)) continue;
			for (const selector of closeSelectors) {
				for (const btn of portal.querySelectorAll(selector)) {
					if (isVisible(btn)) {
						btn.click();
						closed += 1;
					}
				}
			}
		}
		return closed;
	};

	const dismissOnce = () => {
		let closed = dismissPortalButtons();
		const modals = findModals();
		for (const modal of [...modals].reverse()) {
			if (hasLoginFields(modal)) continue;
			const btn = findCloseButton(modal);
			if (btn) {
				btn.click();
				closed += 1;
			}
		}
		return closed;
	};
"""

_DISMISS_MODALS_JS = f"""() => {{
{_DISMISS_MODALS_CORE_JS}
	let total = 0;
	for (let round = 0; round < 5; round += 1) {{
		const closed = dismissOnce();
		if (closed === 0) break;
		total += closed;
	}}
	return total;
}}"""

_POPUP_GUARD_INIT_SCRIPT = f"""() => {{
	if (window.__popupGuardInstalled) return;
	window.__popupGuardInstalled = true;
{_DISMISS_MODALS_CORE_JS}
	const dismissLoop = () => {{
		for (let round = 0; round < 3; round += 1) {{
			if (dismissOnce() === 0) break;
		}}
	}};

	let timer = null;
	const scheduleDismiss = () => {{
		clearTimeout(timer);
		timer = setTimeout(dismissLoop, 300);
	}};

	const observer = new MutationObserver(scheduleDismiss);
	const startObserver = () => {{
		if (!document.documentElement) return;
		observer.observe(document.documentElement, {{
			childList: true,
			subtree: true,
			attributes: true,
			attributeFilter: ['class', 'style', 'aria-hidden', 'aria-modal'],
		}});
		scheduleDismiss();
	}};

	if (document.readyState === 'loading') {{
		document.addEventListener('DOMContentLoaded', startObserver, {{ once: true }});
	}} else {{
		startObserver();
	}}

	window.__dismissModals = dismissLoop;
}}"""


async def setup_popup_guard(page: Page) -> None:
	"""为页面注入弹窗自动关闭脚本，后续弹窗由 MutationObserver 处理。"""
	await page.add_init_script(_POPUP_GUARD_INIT_SCRIPT)


async def _dismiss_popups_playwright(page: Page) -> int:
	"""通过 Playwright 定位 Semi 公告弹窗并关闭。"""
	closed = 0

	for _ in range(5):
		modals = page.locator(_MODAL_SELECTOR)
		modal_count = await modals.count()
		visible_indices: list[int] = []
		for index in range(modal_count):
			try:
				if await modals.nth(index).is_visible():
					visible_indices.append(index)
			except Exception:  # nosec B112
				continue

		if not visible_indices:
			break

		round_closed = False
		for index in reversed(visible_indices):
			modal = modals.nth(index)
			try:
				if await modal.locator('form.semi-form, #username, input[type="password"]').count() > 0:
					continue
			except Exception:  # nosec B110
				pass
			for pattern in (_CLOSE_ANNOUNCEMENT, _DISMISS_TODAY):
				button = modal.get_by_role('button', name=pattern).first
				try:
					if await button.is_visible():
						await button.click(timeout=3000)
						closed += 1
						round_closed = True
						break
				except Exception:  # nosec B112
					continue
			else:
				close_button = modal.locator('button.semi-modal-close, button[aria-label="close"]').first
				try:
					if await close_button.is_visible():
						await close_button.click(timeout=3000)
						closed += 1
						round_closed = True
				except Exception:  # nosec B110
					pass

		if not round_closed:
			break
		await asyncio.sleep(0.4)

	return closed


async def dismiss_popups(page: Page) -> int:
	"""手动触发弹窗关闭：优先 Playwright 点公告按钮，再回退 JS。"""
	closed = await _dismiss_popups_playwright(page)
	result = await page.evaluate(_DISMISS_MODALS_JS)
	return closed + (int(result) if result else 0)
