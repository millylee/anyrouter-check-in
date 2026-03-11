// popup.js

let currentMode = 'list'; // 'list' | 'json'

// Provider → domain mapping for import
const PROVIDER_DOMAINS = {
  anyrouter:    'https://anyrouter.top',
  agentrouter:  'https://agentrouter.org',
  freestyle:    'https://api.freestyle.cc.cd',
  xingyungept:  'https://ai.xingyungept.cn',
  sorai:        'https://newapi.sorai.me',
  apikey:       'https://welfare.apikey.cc',
};

document.addEventListener('DOMContentLoaded', async () => {
  const config = await chrome.storage.sync.get([
    'githubToken', 'repoOwner', 'repoName', 'environmentName', 'accounts', 'refreshInterval'
  ]);

  setVal('githubToken', config.githubToken || '');
  setVal('repoOwner',   config.repoOwner   || '');
  setVal('repoName',    config.repoName    || 'anyrouter-check-in');
  setVal('environmentName', config.environmentName !== undefined ? config.environmentName : 'production');
  if (config.refreshInterval) setVal('refreshInterval', config.refreshInterval);

  let accounts = [];
  try {
    accounts = config.accounts
      ? (typeof config.accounts === 'string' ? JSON.parse(config.accounts) : config.accounts)
      : [];
  } catch { accounts = []; }

  renderList(accounts);
  renderJson(accounts);

  document.getElementById('tabList').addEventListener('click', () => switchTab('list'));
  document.getElementById('tabJson').addEventListener('click', () => switchTab('json'));
  document.getElementById('addAccountBtn').addEventListener('click', () => addAccountItem({}));
  document.getElementById('saveBtn').addEventListener('click', save);
  document.getElementById('syncBtn').addEventListener('click', syncNow);
  document.getElementById('logsBtn').addEventListener('click', () => { window.location.href = 'logs.html'; });
  document.getElementById('importBtn').addEventListener('click', openImportDialog);

  // Live JSON validation
  document.getElementById('jsonTextarea').addEventListener('input', () => {
    const raw = document.getElementById('jsonTextarea').value.trim();
    const errEl = document.getElementById('jsonErr');
    if (!raw) { errEl.style.display = 'none'; return; }
    try { JSON.parse(raw); errEl.style.display = 'none'; }
    catch { errEl.style.display = 'block'; }
  });
});

// ---- Tab switch ----

function switchTab(mode) {
  if (mode === currentMode) return;

  if (mode === 'json') {
    const accounts = collectFromList();
    renderJson(accounts);
    document.getElementById('listMode').style.display = 'none';
    document.getElementById('jsonMode').style.display = '';
    document.getElementById('tabList').classList.remove('active');
    document.getElementById('tabJson').classList.add('active');
  } else {
    // Treat empty textarea as empty array — no JSON error on blank
    const raw = document.getElementById('jsonTextarea').value.trim();
    let accounts = [];
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed)) throw new Error();
        accounts = parsed;
      } catch {
        showStatus('JSON 格式有误，无法切换到列表模式', 'error');
        return;
      }
    }
    renderList(accounts);
    document.getElementById('jsonMode').style.display = 'none';
    document.getElementById('listMode').style.display = '';
    document.getElementById('tabJson').classList.remove('active');
    document.getElementById('tabList').classList.add('active');
    document.getElementById('jsonErr').style.display = 'none';
  }
  currentMode = mode;
}

// ---- List mode ----

function renderList(accounts) {
  const list = document.getElementById('accountList');
  list.innerHTML = '';
  if (!accounts || accounts.length === 0) {
    addAccountItem({});
  } else {
    accounts.forEach(a => addAccountItem(a));
  }
}

function addAccountItem(data = {}) {
  const list = document.getElementById('accountList');
  const idx  = list.children.length + 1;
  const item = document.createElement('div');
  item.className = 'account-item';
  // cookie_name defaults to 'session', no extra label text needed
  const cookieNameVal = esc(data.cookie_name || 'session');
  item.innerHTML = `
    <div class="account-item-header">
      <span class="account-item-label">账号 ${idx}</span>
      <button class="account-item-del" title="删除" type="button">✕</button>
    </div>
    <div class="account-row">
      <div class="field-wrap" style="flex:2">
        <label>domain（必填）</label>
        <input type="text" class="f-domain" placeholder="https://anyrouter.top" value="${esc(data.domain || '')}">
      </div>
      <div class="field-wrap">
        <label>cookie_name</label>
        <input type="text" class="f-cookie_name" placeholder="session" value="${cookieNameVal}">
      </div>
    </div>
    <div class="account-row">
      <div class="field-wrap">
        <label>api_user（可留空自动获取）</label>
        <input type="text" class="f-api_user" placeholder="自动" value="${esc(data.api_user || '')}">
      </div>
      <div class="field-wrap">
        <label>env_key_suffix（可留空）</label>
        <input type="text" class="f-env_key_suffix" placeholder="自动生成 api_user_PROVIDER" value="${esc(data.env_key_suffix || '')}">
      </div>
    </div>
    <input type="hidden" class="f-imported-session" value="${esc(data._imported_session || '')}">
  `;
  item.querySelector('.account-item-del').addEventListener('click', () => {
    item.remove();
    reindexList();
  });
  list.appendChild(item);
}

function reindexList() {
  document.querySelectorAll('.account-item').forEach((item, i) => {
    const label = item.querySelector('.account-item-label');
    if (label) label.textContent = `账号 ${i + 1}`;
  });
}

function collectFromList() {
  return Array.from(document.querySelectorAll('.account-item')).map(item => {
    const domain = item.querySelector('.f-domain').value.trim();
    if (!domain) return null;
    const entry = { domain };
    const api_user        = item.querySelector('.f-api_user').value.trim();
    const env_key_suffix  = item.querySelector('.f-env_key_suffix').value.trim();
    const cookie_name     = item.querySelector('.f-cookie_name').value.trim();
    const importedSession = item.querySelector('.f-imported-session')?.value || '';
    if (api_user)        entry.api_user        = api_user;
    if (env_key_suffix)  entry.env_key_suffix  = env_key_suffix;
    if (cookie_name && cookie_name !== 'session') entry.cookie_name = cookie_name;
    if (importedSession) entry._imported_session = importedSession;
    return entry;
  }).filter(Boolean);
}

// ---- JSON mode ----

function renderJson(accounts) {
  const ta    = document.getElementById('jsonTextarea');
  const errEl = document.getElementById('jsonErr');
  ta.value = (accounts && accounts.length > 0) ? JSON.stringify(accounts, null, 2) : '';
  errEl.style.display = 'none';
}

function collectFromJson() {
  const raw   = document.getElementById('jsonTextarea').value.trim();
  const errEl = document.getElementById('jsonErr');
  if (!raw) { errEl.style.display = 'none'; return []; }
  try {
    const data = JSON.parse(raw);
    if (!Array.isArray(data)) throw new Error('not array');
    errEl.style.display = 'none';
    return data;
  } catch {
    errEl.style.display = 'block';
    return null;
  }
}

// ---- Import from ANYROUTER_ACCOUNTS ----

function openImportDialog() {
  if (document.getElementById('importOverlay')) return;

  const overlay = document.createElement('div');
  overlay.id = 'importOverlay';
  overlay.style.cssText = `
    position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;
    display:flex;align-items:center;justify-content:center;
  `;

  const box = document.createElement('div');
  box.style.cssText = `
    background:#fff;border-radius:8px;padding:18px;width:440px;max-width:95vw;
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px;color:#24292f;
    box-shadow:0 8px 32px rgba(0,0,0,.2);
  `;
  box.innerHTML = `
    <div style="font-weight:700;font-size:14px;margin-bottom:10px">
      📥 从 ANYROUTER_ACCOUNTS 导入
    </div>
    <div style="font-size:11px;color:#57606a;margin-bottom:8px;line-height:1.5">
      粘贴 GitHub Secrets 中 <strong>ANYROUTER_ACCOUNTS</strong> 的 JSON 内容（支持多行），
      脚本将自动解析 cookies.session + api_user + provider，转换为本插件所需格式。
    </div>
    <textarea id="importTa" style="
      width:100%;min-height:120px;padding:7px 9px;border:1px solid #d0d7de;border-radius:5px;
      font-family:monospace;font-size:11px;resize:vertical;box-sizing:border-box;background:#f6f8fa;
    " placeholder='[
  {"cookies":{"session":"..."},"api_user":"123456"},
  {"cookies":{"session":"..."},"api_user":"789012","provider":"agentrouter"}
]'></textarea>
    <div id="importErr" style="font-size:11px;color:#cf222e;margin-top:4px;display:none">⚠ JSON 格式错误</div>
    <div style="display:flex;gap:8px;margin-top:12px">
      <button id="importConfirmBtn" style="
        flex:1;padding:7px;background:#0969da;color:#fff;border:none;border-radius:6px;
        font-size:13px;font-weight:500;cursor:pointer;
      ">导入并覆盖当前账号</button>
      <button id="importMergeBtn" style="
        flex:1;padding:7px;background:#2da44e;color:#fff;border:none;border-radius:6px;
        font-size:13px;font-weight:500;cursor:pointer;
      ">导入并合并（去重）</button>
      <button id="importCancelBtn" style="
        padding:7px 14px;background:#f6f8fa;border:1px solid #d0d7de;border-radius:6px;
        font-size:13px;cursor:pointer;
      ">取消</button>
    </div>
  `;
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
  box.querySelector('#importCancelBtn').addEventListener('click', () => overlay.remove());

  const doImport = (merge) => {
    const raw = box.querySelector('#importTa').value.trim();
    const errEl = box.querySelector('#importErr');
    let parsed;
    try {
      parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) throw new Error();
      errEl.style.display = 'none';
    } catch {
      errEl.style.display = 'block';
      return;
    }

    const imported = convertFromAnyRouterAccounts(parsed);
    if (imported.length === 0) {
      errEl.textContent = '未能解析出任何有效账号（需要 cookies.session 字段）';
      errEl.style.display = 'block';
      return;
    }

    let final = imported;
    if (merge) {
      const existing = currentMode === 'list' ? collectFromList() : (collectFromJson() || []);
      // Deduplicate by api_user, imported takes precedence
      const byApiUser = {};
      [...existing, ...imported].forEach(a => {
        const key = a.api_user || a.domain;
        byApiUser[key] = a;
      });
      final = Object.values(byApiUser);
    }

    overlay.remove();

    if (currentMode === 'list') {
      renderList(final);
    } else {
      renderJson(final);
    }
    showStatus(`✅ 已导入 ${imported.length} 个账号${merge ? '（已合并去重）' : ''}`, 'success');
  };

  box.querySelector('#importConfirmBtn').addEventListener('click', () => doImport(false));
  box.querySelector('#importMergeBtn').addEventListener('click',  () => doImport(true));
}

/**
 * Convert ANYROUTER_ACCOUNTS format to plugin format.
 * Input:  [{cookies:{session:"..."}, api_user:"xxx", provider:"anyrouter"}, ...]
 * Output: [{domain:"https://...", api_user:"xxx", env_key_suffix:"xxx_ANYROUTER"}, ...]
 *
 * Secret naming: always {api_user}_{PROVIDER} to avoid cross-platform ID collisions.
 */
function convertFromAnyRouterAccounts(items) {
  return items.map(item => {
    const sessionCookie = item?.cookies?.session;
    if (!sessionCookie) return null;

    const provider = item.provider || 'anyrouter';
    const domain   = PROVIDER_DOMAINS[provider] || null;
    if (!domain) return null;

    const entry = { domain };
    if (item.api_user) {
      entry.api_user = String(item.api_user);
      // Always use {api_user}_{PROVIDER} — IDs are per-platform and can collide across providers
      entry.env_key_suffix = `${item.api_user}_${provider.toUpperCase()}`;
    }
    // Store the actual session value so background.js can use it directly
    // (no need to re-extract from browser if we already have it)
    entry._imported_session = sessionCookie;
    return entry;
  }).filter(Boolean);
}

// ---- Collect accounts from current mode ----

function collectAccounts() {
  return currentMode === 'json' ? collectFromJson() : collectFromList();
}

// ---- Save ----

async function save() {
  const githubToken    = getVal('githubToken');
  const repoOwner      = getVal('repoOwner');
  const repoName       = getVal('repoName') || 'anyrouter-check-in';
  const environmentName = getVal('environmentName');
  const refreshInterval = parseInt(document.getElementById('refreshInterval').value) || 360;

  if (!githubToken || !repoOwner) {
    showStatus('请填写 GitHub Token 和 Owner', 'error'); return;
  }
  if (refreshInterval < 30 || refreshInterval > 1440) {
    showStatus('同步间隔需在 30–1440 分钟之间', 'error'); return;
  }

  const accounts = collectAccounts();
  if (accounts === null) {
    showStatus('账号 JSON 格式有误，请检查', 'error'); return;
  }

  await chrome.storage.sync.set({
    githubToken, repoOwner, repoName, environmentName,
    accounts: JSON.stringify(accounts),
    refreshInterval
  });
  chrome.runtime.sendMessage({ action: 'updateConfig' });
  showStatus(`✅ 配置已保存（${accounts.length} 个账号）`, 'success');
}

// ---- Sync now ----

function syncNow() {
  showStatus('正在同步...', 'info');
  chrome.runtime.sendMessage({ action: 'syncNow' }, (response) => {
    if (response && response.success) {
      showStatus(`✅ ${response.summary}`, 'success');
    } else {
      showStatus(`❌ ${response ? response.error || response.summary : '未知错误'}`, 'error');
    }
  });
}

// ---- Helpers ----

function getVal(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}
function setVal(id, v) {
  const el = document.getElementById(id);
  if (el) el.value = v;
}
function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
}
function showStatus(message, type) {
  const el = document.getElementById('status');
  el.textContent = message;
  el.className = `status ${type}`;
  el.style.display = 'block';
  if (type !== 'info') setTimeout(() => { el.style.display = 'none'; }, 5000);
}
