// popup.js

let currentMode = 'list'; // 'list' | 'json'

document.addEventListener('DOMContentLoaded', async () => {
  const config = await chrome.storage.sync.get([
    'githubToken', 'repoOwner', 'repoName', 'environmentName', 'accounts', 'refreshInterval'
  ]);

  // Fill GitHub fields
  setVal('githubToken', config.githubToken || '');
  setVal('repoOwner', config.repoOwner || '');
  setVal('repoName', config.repoName || '');
  setVal('environmentName', config.environmentName !== undefined ? config.environmentName : 'production');
  if (config.refreshInterval) setVal('refreshInterval', config.refreshInterval);

  // Load accounts
  let accounts = [];
  try {
    accounts = config.accounts ? (typeof config.accounts === 'string' ? JSON.parse(config.accounts) : config.accounts) : [];
  } catch { accounts = []; }

  renderList(accounts);
  renderJson(accounts);

  // Tab switching
  document.getElementById('tabList').addEventListener('click', () => switchTab('list'));
  document.getElementById('tabJson').addEventListener('click', () => switchTab('json'));

  document.getElementById('addAccountBtn').addEventListener('click', () => {
    addAccountItem({});
  });

  document.getElementById('saveBtn').addEventListener('click', save);
  document.getElementById('syncBtn').addEventListener('click', syncNow);
  document.getElementById('logsBtn').addEventListener('click', () => { window.location.href = 'logs.html'; });
});

// ---- Tab switch ----

function switchTab(mode) {
  if (mode === currentMode) return;

  if (mode === 'json') {
    // Collect from list → update JSON textarea
    const accounts = collectFromList();
    renderJson(accounts);
    document.getElementById('listMode').style.display = 'none';
    document.getElementById('jsonMode').style.display = '';
    document.getElementById('tabList').classList.remove('active');
    document.getElementById('tabJson').classList.add('active');
  } else {
    // Parse JSON → render list
    const accounts = collectFromJson();
    if (accounts === null) {
      showStatus('JSON 格式有误，无法切换到列表模式', 'error');
      return;
    }
    renderList(accounts);
    document.getElementById('jsonMode').style.display = 'none';
    document.getElementById('listMode').style.display = '';
    document.getElementById('tabJson').classList.remove('active');
    document.getElementById('tabList').classList.add('active');
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
  const idx = list.children.length + 1;
  const item = document.createElement('div');
  item.className = 'account-item';
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
        <input type="text" class="f-cookie_name" placeholder="session" value="${esc(data.cookie_name || '')}">
      </div>
    </div>
    <div class="account-row">
      <div class="field-wrap">
        <label>api_user（可留空自动获取）</label>
        <input type="text" class="f-api_user" placeholder="自动" value="${esc(data.api_user || '')}">
      </div>
      <div class="field-wrap">
        <label>env_key_suffix（可留空）</label>
        <input type="text" class="f-env_key_suffix" placeholder="默认用 api_user" value="${esc(data.env_key_suffix || '')}">
      </div>
    </div>
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
  const items = document.querySelectorAll('.account-item');
  const accounts = [];
  items.forEach(item => {
    const domain = item.querySelector('.f-domain').value.trim();
    if (!domain) return;
    const entry = { domain };
    const api_user = item.querySelector('.f-api_user').value.trim();
    const env_key_suffix = item.querySelector('.f-env_key_suffix').value.trim();
    const cookie_name = item.querySelector('.f-cookie_name').value.trim();
    if (api_user) entry.api_user = api_user;
    if (env_key_suffix) entry.env_key_suffix = env_key_suffix;
    if (cookie_name) entry.cookie_name = cookie_name;
    accounts.push(entry);
  });
  return accounts;
}

// ---- JSON mode ----

function renderJson(accounts) {
  document.getElementById('jsonTextarea').value = JSON.stringify(accounts, null, 2);
  document.getElementById('jsonErr').style.display = 'none';
}

function collectFromJson() {
  const raw = document.getElementById('jsonTextarea').value.trim();
  const errEl = document.getElementById('jsonErr');
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

document.addEventListener('DOMContentLoaded', () => {
  // Live JSON validation
  const ta = document.getElementById('jsonTextarea');
  if (ta) {
    ta.addEventListener('input', () => {
      const raw = ta.value.trim();
      const errEl = document.getElementById('jsonErr');
      try { JSON.parse(raw); errEl.style.display = 'none'; } catch { errEl.style.display = 'block'; }
    });
  }
});

// ---- Collect accounts from current mode ----

function collectAccounts() {
  if (currentMode === 'json') {
    return collectFromJson();
  } else {
    return collectFromList();
  }
}

// ---- Save ----

async function save() {
  const githubToken = getVal('githubToken');
  const repoOwner = getVal('repoOwner');
  const repoName = getVal('repoName');
  const environmentName = getVal('environmentName');
  const refreshInterval = parseInt(document.getElementById('refreshInterval').value) || 360;

  if (!githubToken || !repoOwner || !repoName) {
    showStatus('请填写 GitHub Token、Owner 和仓库名', 'error'); return;
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
  return String(s).replace(/"/g, '&quot;').replace(/</g, '&lt;');
}

function showStatus(message, type) {
  const el = document.getElementById('status');
  el.textContent = message;
  el.className = `status ${type}`;
  el.style.display = 'block';
  if (type !== 'info') setTimeout(() => { el.style.display = 'none'; }, 5000);
}
