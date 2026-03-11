document.addEventListener('DOMContentLoaded', async () => {
  const fields = ['githubToken', 'repoOwner', 'repoName', 'environmentName', 'accounts', 'refreshInterval'];
  const config = await chrome.storage.sync.get(fields);

  for (const key of fields) {
    const el = document.getElementById(key);
    if (!el) continue;
    if (key === 'accounts' && config[key]) {
      el.value = typeof config[key] === 'string' ? config[key] : JSON.stringify(config[key], null, 2);
    } else if (config[key] !== undefined) {
      el.value = config[key];
    }
  }

  document.getElementById('saveBtn').addEventListener('click', async () => {
    const githubToken = val('githubToken');
    const repoOwner = val('repoOwner');
    const repoName = val('repoName');
    const environmentName = val('environmentName');
    const accountsRaw = val('accounts');
    const refreshInterval = parseInt(document.getElementById('refreshInterval').value) || 360;

    if (!githubToken || !repoOwner || !repoName) {
      showStatus('请填写 GitHub Token、Owner 和仓库名', 'error');
      return;
    }

    let accounts;
    try {
      accounts = JSON.parse(accountsRaw);
      if (!Array.isArray(accounts)) throw new Error('must be array');
    } catch (e) {
      showStatus('账号配置必须是合法的 JSON 数组', 'error');
      return;
    }

    if (refreshInterval < 30 || refreshInterval > 1440) {
      showStatus('同步间隔需在 30-1440 分钟之间', 'error');
      return;
    }

    await chrome.storage.sync.set({
      githubToken, repoOwner, repoName, environmentName,
      accounts: JSON.stringify(accounts),
      refreshInterval
    });

    chrome.runtime.sendMessage({ action: 'updateConfig' });
    showStatus('✅ 配置已保存', 'success');
  });

  document.getElementById('syncBtn').addEventListener('click', async () => {
    showStatus('正在同步...', 'info');
    chrome.runtime.sendMessage({ action: 'syncNow' }, (response) => {
      if (response && response.success) {
        showStatus(`✅ ${response.summary}`, 'success');
      } else {
        showStatus(`❌ ${response ? response.error || response.summary : '未知错误'}`, 'error');
      }
    });
  });

  document.getElementById('logsBtn').addEventListener('click', () => {
    window.location.href = 'logs.html';
  });
});

function val(id) {
  const el = document.getElementById(id);
  return el ? el.value.trim() : '';
}

function showStatus(message, type) {
  const el = document.getElementById('status');
  el.textContent = message;
  el.className = `status ${type}`;
  el.style.display = 'block';
  if (type !== 'info') setTimeout(() => { el.style.display = 'none'; }, 5000);
}
