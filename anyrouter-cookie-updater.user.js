// ==UserScript==
// @name         AnyRouter Cookie Updater
// @namespace    https://github.com/shenhao-stu/anyrouter-check-in
// @version      1.0.0
// @description  自动提取已登录 AnyRouter 等 NewAPI/OneAPI 平台的 session cookie，推送到 GitHub Actions Environment Secrets（ANYROUTER_ACCOUNT_* 格式），配合签到脚本实现 cookie 自动续期。
// @author       shenhao-stu
// @license      MIT
//
// @match        https://anyrouter.top/*
// @match        https://agentrouter.org/*
// @match        https://api.freestyle.cc.cd/*
// @match        https://ai.xingyungept.cn/*
// @match        https://newapi.sorai.me/*
// @match        https://welfare.apikey.cc/*
//
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_deleteValue
// @grant        GM_listValues
// @grant        GM_cookie
// @grant        GM_xmlhttpRequest
// @grant        GM_registerMenuCommand
// @grant        GM_notification
// @grant        GM_addStyle
//
// @connect      api.github.com
// @connect      *
//
// @require      https://cdn.jsdelivr.net/npm/tweetnacl@1.0.3/nacl-fast.min.js
//
// @run-at       document-idle
// ==/UserScript==

(function () {
  'use strict';

  // ──────────────────────────────────────────────
  //  Constants
  // ──────────────────────────────────────────────
  const SCRIPT_NAME = 'AnyRouter Cookie Updater';
  const CFG_KEY = 'anyrouter_cookie_updater_config';
  const LOG_KEY = 'anyrouter_cookie_updater_logs';
  const LAST_SYNC_KEY = 'anyrouter_cookie_updater_last_sync';
  const MAX_LOGS = 80;

  // ──────────────────────────────────────────────
  //  Config helpers
  // ──────────────────────────────────────────────
  function loadConfig() {
    const raw = GM_getValue(CFG_KEY, '{}');
    try { return JSON.parse(raw); } catch { return {}; }
  }

  function saveConfig(cfg) {
    GM_setValue(CFG_KEY, JSON.stringify(cfg));
  }

  // ──────────────────────────────────────────────
  //  Logger
  // ──────────────────────────────────────────────
  function getLogs() {
    try { return JSON.parse(GM_getValue(LOG_KEY, '[]')); } catch { return []; }
  }

  function addLog(level, message, details) {
    const logs = getLogs();
    logs.unshift({ timestamp: new Date().toISOString(), level, message, details: details || null });
    if (logs.length > MAX_LOGS) logs.splice(MAX_LOGS);
    GM_setValue(LOG_KEY, JSON.stringify(logs));
    console.log(`[${SCRIPT_NAME}][${level}]`, message, details || '');
  }

  const log = {
    info: (m, d) => addLog('INFO', m, d),
    error: (m, d) => addLog('ERROR', m, d),
    success: (m, d) => addLog('SUCCESS', m, d),
  };

  // ──────────────────────────────────────────────
  //  Cookie extraction via GM_cookie
  // ──────────────────────────────────────────────
  function getCookieValue(domain, name) {
    return new Promise((resolve) => {
      try {
        GM_cookie.list({ domain: new URL(domain).hostname, name }, (cookies, err) => {
          if (err || !cookies || cookies.length === 0) { resolve(null); return; }
          resolve(cookies[0].value);
        });
      } catch (e) {
        resolve(null);
      }
    });
  }

  // ──────────────────────────────────────────────
  //  Fetch api_user from /api/user/self
  // ──────────────────────────────────────────────
  function fetchApiUser(domain, cookieName, cookieValue) {
    return new Promise((resolve) => {
      GM_xmlhttpRequest({
        method: 'GET',
        url: `${domain.replace(/\/$/, '')}/api/user/self`,
        headers: { 'Accept': 'application/json', 'Cookie': `${cookieName}=${cookieValue}` },
        onload(resp) {
          try {
            const data = JSON.parse(resp.responseText);
            const id = data?.data?.id ?? data?.id ?? null;
            resolve(id != null ? String(id) : null);
          } catch { resolve(null); }
        },
        onerror() { resolve(null); }
      });
    });
  }

  // ──────────────────────────────────────────────
  //  GitHub Secrets encryption (libsodium sealed box via tweetnacl)
  // ──────────────────────────────────────────────
  function base64Decode(str) {
    return Uint8Array.from(atob(str), c => c.charCodeAt(0));
  }

  function base64Encode(bytes) {
    let binary = '';
    for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
    return btoa(binary);
  }

  function sealedBoxNonce(ephemeralPk, recipientPk) {
    const combined = new Uint8Array(ephemeralPk.length + recipientPk.length);
    combined.set(ephemeralPk);
    combined.set(recipientPk, ephemeralPk.length);
    return nacl.hash(combined).slice(0, nacl.box.nonceLength);
  }

  function sealedBox(publicKey, message) {
    const ephemeral = nacl.box.keyPair();
    const nonce = sealedBoxNonce(ephemeral.publicKey, publicKey);
    const encrypted = nacl.box(message, nonce, publicKey, ephemeral.secretKey);
    const result = new Uint8Array(ephemeral.publicKey.length + encrypted.length);
    result.set(ephemeral.publicKey);
    result.set(encrypted, ephemeral.publicKey.length);
    return result;
  }

  function encryptSecret(base64PublicKey, plaintext) {
    const publicKeyBytes = base64Decode(base64PublicKey);
    const msgBytes = new TextEncoder().encode(plaintext);
    return base64Encode(sealedBox(publicKeyBytes, msgBytes));
  }

  // ──────────────────────────────────────────────
  //  GitHub API helpers
  // ──────────────────────────────────────────────
  function ghFetch(token, url, method = 'GET', body = null) {
    return new Promise((resolve, reject) => {
      const details = {
        method,
        url,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Accept': 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        onload(resp) {
          const ok = resp.status >= 200 && resp.status < 300;
          try { resolve({ ok, status: resp.status, data: JSON.parse(resp.responseText) }); }
          catch { resolve({ ok, status: resp.status, data: resp.responseText }); }
        },
        onerror(e) { reject(new Error(`Network error: ${JSON.stringify(e)}`)); }
      };
      if (body) details.data = JSON.stringify(body);
      GM_xmlhttpRequest(details);
    });
  }

  async function getRepoId(cfg) {
    const r = await ghFetch(cfg.githubToken, `https://api.github.com/repos/${cfg.repoOwner}/${cfg.repoName}`);
    if (!r.ok) throw new Error(`Cannot get repo ID: ${r.status}`);
    return r.data.id;
  }

  async function getPublicKey(cfg) {
    let url;
    if (cfg.environmentName) {
      const repoId = await getRepoId(cfg);
      url = `https://api.github.com/repositories/${repoId}/environments/${encodeURIComponent(cfg.environmentName)}/secrets/public-key`;
    } else {
      url = `https://api.github.com/repos/${cfg.repoOwner}/${cfg.repoName}/actions/secrets/public-key`;
    }
    const r = await ghFetch(cfg.githubToken, url);
    if (!r.ok) throw new Error(`Cannot get public key: ${r.status}`);
    return r.data; // { key, key_id }
  }

  async function putSecret(cfg, secretName, secretValue) {
    const { key, key_id } = await getPublicKey(cfg);
    const encrypted_value = encryptSecret(key, secretValue);

    let url;
    if (cfg.environmentName) {
      const repoId = await getRepoId(cfg);
      url = `https://api.github.com/repositories/${repoId}/environments/${encodeURIComponent(cfg.environmentName)}/secrets/${secretName}`;
    } else {
      url = `https://api.github.com/repos/${cfg.repoOwner}/${cfg.repoName}/actions/secrets/${secretName}`;
    }

    const r = await ghFetch(cfg.githubToken, url, 'PUT', { encrypted_value, key_id });
    if (!r.ok) throw new Error(`PUT secret failed: ${r.status} ${JSON.stringify(r.data)}`);
  }

  // ──────────────────────────────────────────────
  //  Core sync logic
  // ──────────────────────────────────────────────
  async function syncCurrentSite() {
    const cfg = loadConfig();
    if (!cfg.githubToken || !cfg.repoOwner || !cfg.repoName) {
      log.error('GitHub config incomplete, open settings first');
      notify('❌ 未配置 GitHub 信息，请点击扩展菜单中的「⚙️ 设置」');
      return { success: false, error: '未配置 GitHub 信息' };
    }

    const accounts = cfg.accounts || [];
    const origin = location.origin;

    // Find account entries matching current site
    const matching = accounts.filter(a => {
      const d = (a.domain || '').replace(/\/$/, '');
      return d === origin || origin.startsWith(d);
    });

    if (matching.length === 0) {
      log.info(`No account configured for ${origin}, skipping`);
      return { success: true, summary: `${origin} 未配置账号，跳过` };
    }

    let successCount = 0;
    for (const account of matching) {
      const result = await syncOneAccount(cfg, account);
      if (result.success) successCount++;
    }

    const summary = `${successCount}/${matching.length} 个账号同步成功`;
    GM_setValue(LAST_SYNC_KEY, new Date().toISOString());
    return { success: successCount > 0, summary };
  }

  async function syncAllSites() {
    const cfg = loadConfig();
    if (!cfg.githubToken || !cfg.repoOwner || !cfg.repoName) {
      log.error('GitHub config incomplete');
      notify('❌ 未配置 GitHub 信息');
      return { success: false, error: '未配置 GitHub 信息' };
    }

    const accounts = cfg.accounts || [];
    if (accounts.length === 0) {
      notify('⚠️ 未配置任何账号');
      return { success: false, error: '未配置任何账号' };
    }

    let successCount = 0;
    for (const account of accounts) {
      const result = await syncOneAccount(cfg, account);
      if (result.success) successCount++;
    }

    const summary = `${successCount}/${accounts.length} 个账号同步成功`;
    GM_setValue(LAST_SYNC_KEY, new Date().toISOString());
    notify(successCount > 0 ? `✅ ${summary}` : `❌ 全部同步失败`);
    log.info('Full sync done', { summary });
    return { success: successCount > 0, summary };
  }

  async function syncOneAccount(cfg, account) {
    const { domain, cookie_name } = account;
    let { api_user, env_key_suffix } = account;
    const targetCookieName = cookie_name || 'session';
    const label = env_key_suffix || api_user || domain;

    try {
      log.info(`Extracting cookie "${targetCookieName}" for ${label}`);

      const cookieValue = await getCookieValue(domain, targetCookieName);
      if (!cookieValue) {
        log.error(`Cookie "${targetCookieName}" not found for ${label}`, { domain });
        return { success: false, label, error: `cookie not found` };
      }

      log.success(`Cookie extracted for ${label}`, { length: cookieValue.length });

      if (!api_user) {
        log.info(`Fetching api_user from /api/user/self for ${label}`);
        api_user = await fetchApiUser(domain, targetCookieName, cookieValue);
        if (api_user) log.success(`Auto-resolved api_user: ${api_user}`);
        else log.info(`api_user not resolved, will omit from secret`);
      }

      const secretSuffix = env_key_suffix || api_user;
      if (!secretSuffix) {
        log.error(`Cannot determine secret name for ${label}`);
        return { success: false, label, error: 'no env_key_suffix or api_user' };
      }

      const secretName = `ANYROUTER_ACCOUNT_${secretSuffix}`;
      const secretValue = JSON.stringify({
        cookies: { [targetCookieName]: cookieValue },
        ...(api_user ? { api_user } : {})
      });

      log.info(`Pushing to GitHub secret: ${secretName}`);
      await putSecret(cfg, secretName, secretValue);
      log.success(`✅ ${secretName} updated`);
      return { success: true, label, secretName };
    } catch (e) {
      log.error(`Failed for ${label}`, { error: e.message });
      return { success: false, label, error: e.message };
    }
  }

  // ──────────────────────────────────────────────
  //  Notification
  // ──────────────────────────────────────────────
  function notify(text) {
    GM_notification({ title: SCRIPT_NAME, text, timeout: 5000 });
  }

  // ──────────────────────────────────────────────
  //  Settings UI
  // ──────────────────────────────────────────────
  GM_addStyle(`
    #arc-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,.5);
      z-index: 2147483646; display: flex; align-items: center; justify-content: center;
    }
    #arc-panel {
      background: #fff; border-radius: 10px; width: 520px; max-height: 90vh;
      overflow-y: auto; padding: 20px 22px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 13px; color: #24292f; box-shadow: 0 16px 48px rgba(0,0,0,.25);
    }
    #arc-panel h2 { font-size: 16px; color: #0969da; margin-bottom: 14px; }
    .arc-section { background: #f6f8fa; border: 1px solid #d0d7de; border-radius: 6px; padding: 12px; margin-bottom: 10px; }
    .arc-section-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .4px; color: #57606a; margin-bottom: 9px; }
    .arc-row { display: flex; gap: 8px; margin-bottom: 7px; }
    .arc-row:last-child { margin-bottom: 0; }
    .arc-field { display: flex; flex-direction: column; flex: 1; gap: 3px; }
    .arc-field label { font-size: 11px; font-weight: 500; color: #57606a; }
    .arc-field input, .arc-field textarea {
      padding: 5px 8px; border: 1px solid #d0d7de; border-radius: 5px;
      font-size: 12px; font-family: inherit; background: #fff;
    }
    .arc-field input:focus, .arc-field textarea:focus { outline: none; border-color: #0969da; }
    .arc-field textarea { min-height: 90px; font-family: monospace; font-size: 11px; resize: vertical; }
    .arc-hint { font-size: 10px; color: #8b949e; line-height: 1.5; }
    .arc-tabs { display: flex; border: 1px solid #d0d7de; border-radius: 5px; overflow: hidden; margin-bottom: 9px; }
    .arc-tab { flex: 1; padding: 5px; font-size: 12px; font-weight: 500; text-align: center; cursor: pointer; background: #f6f8fa; color: #57606a; border: none; }
    .arc-tab.active { background: #0969da; color: #fff; }
    .arc-account-list { display: flex; flex-direction: column; gap: 7px; }
    .arc-item { border: 1px solid #d0d7de; border-radius: 5px; padding: 9px; background: #fff; }
    .arc-item-hdr { display: flex; align-items: center; justify-content: space-between; margin-bottom: 7px; }
    .arc-item-lbl { font-size: 11px; font-weight: 600; color: #57606a; }
    .arc-del { background: none; border: none; cursor: pointer; color: #cf222e; font-size: 14px; padding: 0 3px; border-radius: 4px; }
    .arc-del:hover { background: #ffebe9; }
    .arc-add { width: 100%; padding: 6px; border: 1px dashed #d0d7de; border-radius: 5px; background: none; color: #57606a; font-size: 12px; cursor: pointer; margin-top: 4px; }
    .arc-add:hover { border-color: #0969da; color: #0969da; background: #ddf4ff; }
    .arc-btn-row { display: flex; gap: 7px; margin-top: 12px; }
    .arc-btn { flex: 1; padding: 7px; border: 1px solid transparent; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; }
    .arc-btn-green { background: #2da44e; color: #fff; }
    .arc-btn-green:hover { background: #218838; }
    .arc-btn-blue { background: #0969da; color: #fff; }
    .arc-btn-blue:hover { background: #0860ca; }
    .arc-btn-grey { background: #f6f8fa; border-color: #d0d7de; color: #24292f; }
    .arc-btn-grey:hover { background: #eaeef2; }
    .arc-status { padding: 7px 10px; border-radius: 5px; font-size: 12px; margin-top: 8px; display: none; }
    .arc-status.ok { background: #dafbe1; color: #116329; border: 1px solid #aceebb; }
    .arc-status.err { background: #ffebe9; color: #82071e; border: 1px solid #ffcecb; }
    .arc-status.inf { background: #ddf4ff; color: #0969da; border: 1px solid #b6e3ff; }
    .arc-json-err { font-size: 10px; color: #cf222e; margin-top: 3px; display: none; }
    .arc-log-entry { padding: 6px 8px; border-radius: 4px; margin-bottom: 4px; border-left: 3px solid #d0d7de; font-size: 11px; }
    .arc-log-entry.INFO { border-left-color: #0969da; background: #ddf4ff; }
    .arc-log-entry.SUCCESS { border-left-color: #2da44e; background: #dafbe1; }
    .arc-log-entry.ERROR { border-left-color: #cf222e; background: #ffebe9; }
    .arc-log-meta { display: flex; justify-content: space-between; margin-bottom: 2px; }
    .arc-log-lvl { font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px; color: #fff; }
    .arc-log-lvl.INFO { background: #0969da; }
    .arc-log-lvl.SUCCESS { background: #2da44e; }
    .arc-log-lvl.ERROR { background: #cf222e; }
    .arc-log-time { font-size: 9px; color: #8b949e; }
    .arc-log-details { font-family: monospace; font-size: 10px; color: #57606a; background: rgba(0,0,0,.04); padding: 3px 5px; border-radius: 3px; white-space: pre-wrap; word-break: break-all; max-height: 80px; overflow-y: auto; margin-top: 3px; }
  `);

  let panelMode = 'list'; // 'list' | 'json'
  let panelView = 'settings'; // 'settings' | 'logs'

  function openPanel() {
    if (document.getElementById('arc-overlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'arc-overlay';
    overlay.addEventListener('click', e => { if (e.target === overlay) closePanel(); });

    const panel = document.createElement('div');
    panel.id = 'arc-panel';
    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    renderPanel(panel);
  }

  function closePanel() {
    const el = document.getElementById('arc-overlay');
    if (el) el.remove();
  }

  function renderPanel(panel) {
    const cfg = loadConfig();
    const accounts = cfg.accounts || [];

    if (panelView === 'logs') {
      renderLogsView(panel, cfg);
      return;
    }

    panel.innerHTML = `
      <h2>🔄 AnyRouter Cookie Updater</h2>

      <div class="arc-section">
        <div class="arc-section-title">GitHub 配置</div>
        <div class="arc-row">
          <div class="arc-field" style="flex:2">
            <label>Personal Access Token (PAT)</label>
            <input type="password" id="arc-token" placeholder="ghp_xxxxxxxxxxxx" value="${esc(cfg.githubToken || '')}">
          </div>
        </div>
        <div class="arc-row">
          <div class="arc-field">
            <label>仓库 Owner</label>
            <input type="text" id="arc-owner" placeholder="your-username" value="${esc(cfg.repoOwner || '')}">
          </div>
          <div class="arc-field">
            <label>仓库名称</label>
            <input type="text" id="arc-repo" placeholder="anyrouter-check-in" value="${esc(cfg.repoName || '')}">
          </div>
          <div class="arc-field">
            <label>Environment（可选）</label>
            <input type="text" id="arc-env" placeholder="production" value="${esc(cfg.environmentName ?? 'production')}">
          </div>
        </div>
      </div>

      <div class="arc-section">
        <div class="arc-section-title">账号配置</div>
        <div class="arc-tabs">
          <button class="arc-tab ${panelMode === 'list' ? 'active' : ''}" id="arc-tab-list">📋 列表模式</button>
          <button class="arc-tab ${panelMode === 'json' ? 'active' : ''}" id="arc-tab-json">{ } JSON 模式</button>
        </div>
        <div id="arc-list-mode" style="display:${panelMode === 'list' ? '' : 'none'}">
          <div class="arc-account-list" id="arc-account-list"></div>
          <button class="arc-add" id="arc-add-btn">＋ 添加账号</button>
        </div>
        <div id="arc-json-mode" style="display:${panelMode === 'json' ? '' : 'none'}">
          <div class="arc-field">
            <textarea id="arc-json-ta">${esc(JSON.stringify(accounts, null, 2))}</textarea>
          </div>
          <div class="arc-json-err" id="arc-json-err">⚠ JSON 格式错误</div>
          <div class="arc-hint" style="margin-top:4px">
            domain（必填）· api_user（可选，自动获取）· env_key_suffix（可选）· cookie_name（可选，默认 session）
          </div>
        </div>
      </div>

      <div class="arc-section">
        <div class="arc-section-title">定时设置</div>
        <div class="arc-row">
          <div class="arc-field">
            <label>自动同步间隔（分钟，0 = 仅手动）</label>
            <input type="number" id="arc-interval" value="${cfg.intervalMinutes ?? 0}" min="0" max="1440" style="width:120px">
            <div class="arc-hint">设为 0 则关闭自动同步。当前页面重新加载时会检查是否需要同步。</div>
          </div>
        </div>
      </div>

      <div class="arc-btn-row">
        <button class="arc-btn arc-btn-green" id="arc-save">💾 保存</button>
        <button class="arc-btn arc-btn-blue" id="arc-sync-cur">🔄 同步本站</button>
        <button class="arc-btn arc-btn-blue" id="arc-sync-all">🔄 同步全部</button>
        <button class="arc-btn arc-btn-grey" id="arc-logs-btn">📋 日志</button>
        <button class="arc-btn arc-btn-grey" id="arc-close">✕ 关闭</button>
      </div>
      <div class="arc-status" id="arc-status"></div>
    `;

    // Render account list items
    accounts.forEach(a => addAccountItem(a));

    // Tabs
    panel.querySelector('#arc-tab-list').addEventListener('click', () => switchMode('list', panel));
    panel.querySelector('#arc-tab-json').addEventListener('click', () => switchMode('json', panel));

    // Add account
    panel.querySelector('#arc-add-btn').addEventListener('click', () => addAccountItem({}));

    // JSON live validation
    const jsonTa = panel.querySelector('#arc-json-ta');
    if (jsonTa) jsonTa.addEventListener('input', () => validateJson(panel));

    // Buttons
    panel.querySelector('#arc-save').addEventListener('click', () => saveFromPanel(panel));
    panel.querySelector('#arc-sync-cur').addEventListener('click', async () => {
      arcStatus('正在同步本站...', 'inf');
      const r = await syncCurrentSite();
      arcStatus(r.success ? `✅ ${r.summary}` : `❌ ${r.error || r.summary}`, r.success ? 'ok' : 'err');
    });
    panel.querySelector('#arc-sync-all').addEventListener('click', async () => {
      arcStatus('正在同步所有账号...', 'inf');
      const r = await syncAllSites();
      arcStatus(r.success ? `✅ ${r.summary}` : `❌ ${r.error || r.summary}`, r.success ? 'ok' : 'err');
    });
    panel.querySelector('#arc-logs-btn').addEventListener('click', () => {
      panelView = 'logs';
      renderPanel(panel);
    });
    panel.querySelector('#arc-close').addEventListener('click', closePanel);
  }

  function renderLogsView(panel, cfg) {
    const logs = getLogs();
    panel.innerHTML = `
      <h2>📋 同步日志</h2>
      <div style="display:flex;gap:7px;margin-bottom:10px">
        <button class="arc-btn arc-btn-grey" id="arc-back" style="flex:initial;padding:5px 12px">← 返回</button>
        <button class="arc-btn arc-btn-grey" id="arc-clear-log" style="flex:initial;padding:5px 12px;color:#cf222e">🗑 清空</button>
      </div>
      <div id="arc-log-list" style="max-height:420px;overflow-y:auto">
        ${logs.length === 0 ? '<div style="text-align:center;color:#8b949e;padding:30px">暂无日志</div>' : logs.map(l => `
          <div class="arc-log-entry ${l.level}">
            <div class="arc-log-meta">
              <span class="arc-log-lvl ${l.level}">${l.level}</span>
              <span class="arc-log-time">${formatTime(l.timestamp)}</span>
            </div>
            <div>${l.message}</div>
            ${l.details ? `<div class="arc-log-details">${esc(JSON.stringify(l.details, null, 2))}</div>` : ''}
          </div>
        `).join('')}
      </div>
    `;
    panel.querySelector('#arc-back').addEventListener('click', () => { panelView = 'settings'; renderPanel(panel); });
    panel.querySelector('#arc-clear-log').addEventListener('click', () => {
      if (confirm('确定清空所有日志？')) { GM_setValue(LOG_KEY, '[]'); renderPanel(panel); }
    });
  }

  function addAccountItem(data) {
    const list = document.getElementById('arc-account-list');
    if (!list) return;
    const idx = list.children.length + 1;
    const item = document.createElement('div');
    item.className = 'arc-item';
    item.innerHTML = `
      <div class="arc-item-hdr">
        <span class="arc-item-lbl">账号 ${idx}</span>
        <button class="arc-del" title="删除">✕</button>
      </div>
      <div class="arc-row">
        <div class="arc-field" style="flex:2">
          <label>domain（必填）</label>
          <input type="text" class="f-domain" placeholder="https://anyrouter.top" value="${esc(data.domain || '')}">
        </div>
        <div class="arc-field">
          <label>cookie_name</label>
          <input type="text" class="f-cookie_name" placeholder="session" value="${esc(data.cookie_name || '')}">
        </div>
      </div>
      <div class="arc-row">
        <div class="arc-field">
          <label>api_user（可留空自动获取）</label>
          <input type="text" class="f-api_user" placeholder="自动" value="${esc(data.api_user || '')}">
        </div>
        <div class="arc-field">
          <label>env_key_suffix（可留空）</label>
          <input type="text" class="f-env_key_suffix" placeholder="默认用 api_user" value="${esc(data.env_key_suffix || '')}">
        </div>
      </div>
    `;
    item.querySelector('.arc-del').addEventListener('click', () => {
      item.remove();
      document.querySelectorAll('.arc-item-lbl').forEach((el, i) => { el.textContent = `账号 ${i + 1}`; });
    });
    list.appendChild(item);
  }

  function switchMode(mode, panel) {
    if (mode === panelMode) return;
    if (mode === 'json') {
      const accounts = collectFromList();
      const ta = panel.querySelector('#arc-json-ta');
      if (ta) ta.value = JSON.stringify(accounts, null, 2);
      panel.querySelector('#arc-list-mode').style.display = 'none';
      panel.querySelector('#arc-json-mode').style.display = '';
      panel.querySelector('#arc-tab-list').classList.remove('active');
      panel.querySelector('#arc-tab-json').classList.add('active');
    } else {
      const accounts = collectFromJson(panel);
      if (accounts === null) { arcStatus('JSON 格式有误，无法切换', 'err'); return; }
      panel.querySelector('#arc-account-list').innerHTML = '';
      accounts.forEach(a => addAccountItem(a));
      panel.querySelector('#arc-json-mode').style.display = 'none';
      panel.querySelector('#arc-list-mode').style.display = '';
      panel.querySelector('#arc-tab-json').classList.remove('active');
      panel.querySelector('#arc-tab-list').classList.add('active');
    }
    panelMode = mode;
  }

  function collectFromList() {
    return Array.from(document.querySelectorAll('.arc-item')).map(item => {
      const domain = item.querySelector('.f-domain').value.trim();
      if (!domain) return null;
      const entry = { domain };
      const api_user = item.querySelector('.f-api_user').value.trim();
      const env_key_suffix = item.querySelector('.f-env_key_suffix').value.trim();
      const cookie_name = item.querySelector('.f-cookie_name').value.trim();
      if (api_user) entry.api_user = api_user;
      if (env_key_suffix) entry.env_key_suffix = env_key_suffix;
      if (cookie_name) entry.cookie_name = cookie_name;
      return entry;
    }).filter(Boolean);
  }

  function collectFromJson(panel) {
    const ta = (panel || document).querySelector('#arc-json-ta');
    if (!ta) return [];
    try {
      const data = JSON.parse(ta.value.trim());
      if (!Array.isArray(data)) throw new Error();
      (panel || document).querySelector('#arc-json-err').style.display = 'none';
      return data;
    } catch {
      (panel || document).querySelector('#arc-json-err').style.display = 'block';
      return null;
    }
  }

  function validateJson(panel) {
    const ta = panel.querySelector('#arc-json-ta');
    const err = panel.querySelector('#arc-json-err');
    try { JSON.parse(ta.value.trim()); err.style.display = 'none'; }
    catch { err.style.display = 'block'; }
  }

  function saveFromPanel(panel) {
    const githubToken = panel.querySelector('#arc-token').value.trim();
    const repoOwner = panel.querySelector('#arc-owner').value.trim();
    const repoName = panel.querySelector('#arc-repo').value.trim();
    const environmentName = panel.querySelector('#arc-env').value.trim();
    const intervalMinutes = parseInt(panel.querySelector('#arc-interval').value) || 0;

    if (!githubToken || !repoOwner || !repoName) {
      arcStatus('请填写 GitHub Token、Owner 和仓库名', 'err'); return;
    }

    const accounts = panelMode === 'json' ? collectFromJson(panel) : collectFromList();
    if (accounts === null) { arcStatus('账号 JSON 格式有误', 'err'); return; }

    const cfg = { githubToken, repoOwner, repoName, environmentName, accounts, intervalMinutes };
    saveConfig(cfg);
    arcStatus(`✅ 已保存（${accounts.length} 个账号）`, 'ok');
  }

  function arcStatus(msg, type) {
    const el = document.getElementById('arc-status');
    if (!el) return;
    el.textContent = msg;
    el.className = `arc-status ${type}`;
    el.style.display = 'block';
    if (type !== 'inf') setTimeout(() => { el.style.display = 'none'; }, 5000);
  }

  // ──────────────────────────────────────────────
  //  Auto-sync on page load
  // ──────────────────────────────────────────────
  async function checkAutoSync() {
    const cfg = loadConfig();
    const intervalMinutes = cfg.intervalMinutes || 0;
    if (intervalMinutes <= 0) return;

    const lastSync = GM_getValue(LAST_SYNC_KEY, null);
    if (lastSync) {
      const diffMin = (Date.now() - new Date(lastSync).getTime()) / 60000;
      if (diffMin < intervalMinutes) {
        log.info(`Auto-sync skipped: last sync ${Math.round(diffMin)}m ago (interval: ${intervalMinutes}m)`);
        return;
      }
    }

    log.info(`Auto-sync triggered (interval: ${intervalMinutes}m)`);
    const result = await syncCurrentSite();
    if (result.summary) notify(result.success ? `✅ 自动同步: ${result.summary}` : `❌ 自动同步失败: ${result.error}`);
  }

  // ──────────────────────────────────────────────
  //  Menu commands
  // ──────────────────────────────────────────────
  GM_registerMenuCommand('⚙️ 设置 / 账号配置', openPanel);
  GM_registerMenuCommand('🔄 立即同步本站', async () => {
    const r = await syncCurrentSite();
    notify(r.success ? `✅ ${r.summary}` : `❌ ${r.error || r.summary}`);
  });
  GM_registerMenuCommand('🔄 同步所有账号', syncAllSites);
  GM_registerMenuCommand('📋 查看日志', () => { panelView = 'logs'; openPanel(); });

  // ──────────────────────────────────────────────
  //  Helpers
  // ──────────────────────────────────────────────
  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function formatTime(iso) {
    const d = new Date(iso);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  }

  // ──────────────────────────────────────────────
  //  Init
  // ──────────────────────────────────────────────
  checkAutoSync();

})();
