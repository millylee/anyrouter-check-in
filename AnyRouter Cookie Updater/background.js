importScripts('tweetnacl.min.js');

const ALARM_NAME = 'cookieSync';

const Logger = {
  async log(level, message, details = null) {
    const timestamp = new Date().toISOString();
    const logEntry = { timestamp, level, message, details };
    console.log(`[${level}] ${message}`, details || '');
    const { logs = [] } = await chrome.storage.local.get(['logs']);
    logs.unshift(logEntry);
    if (logs.length > 100) logs.splice(100);
    await chrome.storage.local.set({ logs });
  },
  info(msg, d) { return this.log('INFO', msg, d); },
  error(msg, d) { return this.log('ERROR', msg, d); },
  success(msg, d) { return this.log('SUCCESS', msg, d); },
  async getLogs() { return (await chrome.storage.local.get(['logs'])).logs || []; },
  async clearLogs() { await chrome.storage.local.set({ logs: [] }); }
};

chrome.runtime.onInstalled.addListener(async () => {
  await Logger.info('AnyRouter Cookie Updater installed');
  await setupAlarm();
});

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'updateConfig') {
    setupAlarm().then(() => Logger.info('Config updated, alarm reset'));
  } else if (request.action === 'syncNow') {
    syncAllAccounts().then(sendResponse).catch(e => sendResponse({ success: false, error: e.message }));
    return true;
  } else if (request.action === 'getLogs') {
    Logger.getLogs().then(logs => sendResponse({ success: true, logs }));
    return true;
  } else if (request.action === 'clearLogs') {
    Logger.clearLogs().then(() => sendResponse({ success: true }));
    return true;
  }
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM_NAME) return;
  await Logger.info('Scheduled sync triggered');
  const result = await syncAllAccounts();
  const title = result.success ? '✅ Cookie 同步完成' : '❌ Cookie 同步失败';
  chrome.notifications.create({ type: 'basic', iconUrl: 'icon.png', title, message: result.summary || result.error || '' });
});

async function setupAlarm() {
  await chrome.alarms.clear(ALARM_NAME);
  const { refreshInterval = 360 } = await chrome.storage.sync.get(['refreshInterval']);
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: refreshInterval });
  await Logger.info(`Alarm set: every ${refreshInterval} minutes`);
}

async function getConfig() {
  return chrome.storage.sync.get([
    'githubToken', 'repoOwner', 'repoName', 'environmentName', 'accounts', 'refreshInterval'
  ]);
}

async function syncAllAccounts() {
  _cachedRepoId = null;
  const config = await getConfig();
  if (!config.githubToken || !config.repoOwner || !config.repoName) {
    await Logger.error('GitHub configuration incomplete');
    return { success: false, error: 'GitHub 配置不完整' };
  }

  let accounts;
  try {
    accounts = typeof config.accounts === 'string' ? JSON.parse(config.accounts) : config.accounts;
  } catch (e) {
    await Logger.error('Failed to parse accounts config', { error: e.message });
    return { success: false, error: '账号配置格式错误' };
  }

  if (!Array.isArray(accounts) || accounts.length === 0) {
    await Logger.error('No accounts configured');
    return { success: false, error: '未配置任何账号' };
  }

  const results = [];
  for (const account of accounts) {
    const result = await syncOneAccount(config, account);
    results.push(result);
  }

  const okCount = results.filter(r => r.success).length;
  const summary = `${okCount}/${results.length} 账号同步成功`;
  await Logger.info('Sync completed', { summary });
  return { success: okCount > 0, summary, results };
}

async function fetchApiUser(domain, cookieName, cookieValue) {
  // Attempt to resolve api_user by calling /api/user/self with the session cookie.
  // Returns the string user id, or null if unavailable.
  try {
    const url = `${domain.replace(/\/$/, '')}/api/user/self`;
    const resp = await fetch(url, {
      headers: {
        'Cookie': `${cookieName}=${cookieValue}`,
        'Accept': 'application/json'
      },
      credentials: 'omit'
    });
    if (!resp.ok) return null;
    const data = await resp.json();
    // Both new-api and one-api return data.data.id or data.id
    const id = data?.data?.id ?? data?.id ?? null;
    return id != null ? String(id) : null;
  } catch {
    return null;
  }
}

// Reverse map: domain → provider name, for auto-generating env_key_suffix
const DOMAIN_TO_PROVIDER = {
  'https://anyrouter.top':       'ANYROUTER',
  'https://agentrouter.org':     'AGENTROUTER',
  'https://api.freestyle.cc.cd': 'FREESTYLE',
  'https://ai.xingyungept.cn':   'XINGYUNGEPT',
  'https://newapi.sorai.me':     'SORAI',
  'https://welfare.apikey.cc':   'APIKEY',
};

async function syncOneAccount(config, account) {
  const { domain, cookie_name } = account;
  let { api_user, env_key_suffix } = account;
  const targetCookieName = cookie_name || 'session';
  const label = env_key_suffix || api_user || domain;

  try {
    let cookieValue = account._imported_session || null;

    if (cookieValue) {
      await Logger.info(`Using imported cookie for ${label}`, { source: 'import' });
    } else {
      await Logger.info(`Extracting cookie "${targetCookieName}" for ${label}`, { domain });

      const url = domain.replace(/\/$/, '');
      const cookies = await chrome.cookies.getAll({ url });
      const cookie = cookies.find(c => c.name === targetCookieName);

      if (!cookie) {
        await Logger.error(`Cookie "${targetCookieName}" not found for ${label}`, {
          available: cookies.map(c => c.name)
        });
        return { success: false, label, error: `cookie "${targetCookieName}" not found` };
      }

      cookieValue = cookie.value;
      await Logger.success(`Cookie extracted for ${label}`, { length: cookieValue.length });
    }

    // Auto-resolve api_user if not provided
    if (!api_user) {
      await Logger.info(`api_user not set for ${label}, fetching from /api/user/self...`);
      api_user = await fetchApiUser(domain, targetCookieName, cookieValue);
      if (api_user) {
        await Logger.success(`Auto-resolved api_user: ${api_user}`);
      } else {
        await Logger.info(`Could not auto-resolve api_user`);
      }
    }

    // Determine secret suffix: always use {api_user}_{PROVIDER} format to avoid
    // cross-platform ID collisions (same numeric ID can exist on different platforms).
    // env_key_suffix takes priority if explicitly set (e.g. for custom/unknown providers).
    if (!env_key_suffix) {
      if (!api_user) {
        await Logger.error(`Cannot determine secret name for ${label}: no env_key_suffix and api_user unavailable`);
        return { success: false, label, error: 'cannot determine secret name (no env_key_suffix, api_user unavailable)' };
      }
      const providerTag = DOMAIN_TO_PROVIDER[domain.replace(/\/$/, '')] || 'UNKNOWN';
      env_key_suffix = `${api_user}_${providerTag}`;
      await Logger.info(`Auto-generated env_key_suffix: ${env_key_suffix}`);
    }

    const secretName = `ANYROUTER_ACCOUNT_${env_key_suffix}`;
    const secretValue = JSON.stringify({
      cookies: { [targetCookieName]: cookieValue },
      ...(api_user ? { api_user } : {})
    });

    await Logger.info(`Pushing to GitHub secret: ${secretName}`);
    await pushToGitHubSecret(config, secretName, secretValue);
    await Logger.success(`✅ ${label}: ${secretName} updated`);
    return { success: true, label, secretName };
  } catch (e) {
    await Logger.error(`Failed for ${label}`, { error: e.message });
    return { success: false, label, error: e.message };
  }
}

// --- GitHub Secrets Encryption (libsodium sealed box via tweetnacl) ---

function sealedBox(publicKey, message) {
  const ephemeral = nacl.box.keyPair();
  const nonce = sealedBoxNonce(ephemeral.publicKey, publicKey);
  const encrypted = nacl.box(message, nonce, publicKey, ephemeral.secretKey);
  const result = new Uint8Array(ephemeral.publicKey.length + encrypted.length);
  result.set(ephemeral.publicKey);
  result.set(encrypted, ephemeral.publicKey.length);
  return result;
}

function sealedBoxNonce(ephemeralPk, recipientPk) {
  const combined = new Uint8Array(ephemeralPk.length + recipientPk.length);
  combined.set(ephemeralPk);
  combined.set(recipientPk, ephemeralPk.length);
  return nacl.hash(combined).slice(0, nacl.box.nonceLength);
}

function base64Decode(str) {
  return Uint8Array.from(atob(str), c => c.charCodeAt(0));
}

function base64Encode(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

let _cachedRepoId = null;
async function getRepoId(config) {
  if (_cachedRepoId) return _cachedRepoId;
  const { githubToken, repoOwner, repoName } = config;
  const resp = await fetch(`https://api.github.com/repos/${repoOwner}/${repoName}`, {
    headers: { Authorization: `Bearer ${githubToken}`, Accept: 'application/vnd.github+json' }
  });
  if (!resp.ok) throw new Error(`Failed to get repo: ${resp.status}`);
  _cachedRepoId = (await resp.json()).id;
  return _cachedRepoId;
}

async function getPublicKey(config) {
  const { githubToken, repoOwner, repoName, environmentName } = config;
  let url;
  if (environmentName) {
    const repoId = await getRepoId(config);
    url = `https://api.github.com/repositories/${repoId}/environments/${encodeURIComponent(environmentName)}/secrets/public-key`;
  } else {
    url = `https://api.github.com/repos/${repoOwner}/${repoName}/actions/secrets/public-key`;
  }
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${githubToken}`, Accept: 'application/vnd.github+json' }
  });
  if (!resp.ok) throw new Error(`Failed to get public key: ${resp.status} ${await resp.text()}`);
  return resp.json();
}

async function pushToGitHubSecret(config, secretName, secretValue) {
  const { githubToken, repoOwner, repoName, environmentName } = config;
  const { key, key_id } = await getPublicKey(config);

  const publicKeyBytes = base64Decode(key);
  const secretBytes = new TextEncoder().encode(secretValue);
  const sealed = sealedBox(publicKeyBytes, secretBytes);
  const encryptedValue = base64Encode(sealed);

  let url;
  if (environmentName) {
    const repoId = await getRepoId(config);
    url = `https://api.github.com/repositories/${repoId}/environments/${encodeURIComponent(environmentName)}/secrets/${secretName}`;
  } else {
    url = `https://api.github.com/repos/${repoOwner}/${repoName}/actions/secrets/${secretName}`;
  }

  const resp = await fetch(url, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${githubToken}`,
      Accept: 'application/vnd.github+json',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ encrypted_value: encryptedValue, key_id })
  });

  if (!resp.ok) throw new Error(`GitHub API ${resp.status}: ${await resp.text()}`);
}
