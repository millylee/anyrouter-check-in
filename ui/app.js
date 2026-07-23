const DATA_URL = 'data/latest.json';

async function loadData() {
  try {
    const res = await fetch(DATA_URL, { cache: 'no-store' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (err) {
    console.error('Failed to load data:', err);
    return null;
  }
}

function formatMoney(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  return `$${Number(val).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatNumber(val) {
  if (val === null || val === undefined || isNaN(val)) return '--';
  return Number(val).toLocaleString('en-US');
}

function formatDateTime(iso) {
  if (!iso) return '--';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}/${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function formatShortTime(iso) {
  if (!iso) return '--';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function renderSummary(summary) {
  document.getElementById('totalAccounts').textContent = formatNumber(summary.total_accounts);
  document.getElementById('checkedToday').textContent = formatNumber(summary.checked_in_today);
  document.getElementById('failedAccounts').textContent = formatNumber(summary.failed_accounts);
  document.getElementById('sessionExpired').textContent = formatNumber(summary.session_expired);

  document.getElementById('totalBalance').textContent = formatMoney(summary.total_balance);
  document.getElementById('totalUsed').textContent = formatMoney(summary.total_used);
  document.getElementById('totalQuota').textContent = formatMoney(summary.total_quota);
  document.getElementById('queriedCount').textContent = `${formatNumber(summary.queried_count)}/${formatNumber(summary.total_accounts)}`;

  document.getElementById('totalRequests').textContent = formatNumber(summary.total_requests);
  document.getElementById('requestUsedQuota').textContent = formatMoney(summary.request_used_quota);
  document.getElementById('usQueried').textContent = `${formatNumber(summary.queried_count)}/${formatNumber(summary.total_accounts)}`;
  document.getElementById('lastQueryTime').textContent = formatShortTime(summary.last_query_time);

  document.getElementById('totalRuns').textContent = formatNumber(summary.total_runs);
  document.getElementById('lastRunTime').textContent = formatShortTime(summary.last_run_time);
  const notifyEl = document.getElementById('notifyStatus');
  notifyEl.textContent = summary.notify_status || '--';
  notifyEl.className = 'stat-value status-badge ' + (summary.notify_status === '已配置' ? 'success' : '');
  document.getElementById('retryInterval').textContent = summary.retry_interval_minutes
    ? `${summary.retry_interval_minutes}分钟`
    : '--';
}

function renderAccountList(accounts, timestamp) {
  const tbody = document.getElementById('accountTbody');
  if (!accounts || accounts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="loading">暂无数据</td></tr>';
    document.getElementById('listInfo').textContent = '暂无账号';
    return;
  }

  document.getElementById('listInfo').textContent = `显示 1-${accounts.length} / 共 ${accounts.length} 个账号，每页 10 条`;

  const rows = accounts.map((acc, idx) => {
    const statusClass = acc.check_in_success ? 'normal' : 'error';
    const statusText = acc.status || (acc.check_in_success ? '正常' : '异常');
    const checkinMsg = acc.check_in_message || '';
    const checkinTime = acc.last_check_in || timestamp;
    const requests = acc.requests || 0;

    return `
      <tr>
        <td><span class="drag-handle">⋮⋮</span></td>
        <td>
          <div class="account-name">${escapeHtml(acc.name)}</div>
          <div class="account-provider">${escapeHtml(acc.provider || '')}</div>
        </td>
        <td><span class="mono">${escapeHtml(acc.api_user || '---')}</span></td>
        <td><span class="mono">${escapeHtml(truncate(acc.cookie_preview || '---', 36))}</span></td>
        <td>
          <span class="status-pill ${statusClass}">${statusText}</span>
          ${checkinMsg ? `<div class="checkin-msg">${escapeHtml(checkinMsg)}</div>` : ''}
        </td>
        <td>
          <div class="balance-info">
            <div class="balance-item">
              <span class="label">余额</span>
              <span class="value">${formatMoney(acc.balance)}</span>
            </div>
            <div class="balance-item">
              <span class="label">已用</span>
              <span class="value">${formatMoney(acc.used)}</span>
            </div>
            <div class="balance-item">
              <span class="label">总额</span>
              <span class="value">${formatMoney(acc.total_quota)}</span>
            </div>
            <div class="balance-item">
              <span class="label">请求</span>
              <span class="value">${formatNumber(requests)} 次</span>
            </div>
            <div class="balance-time">${formatDateTime(checkinTime)}</div>
          </div>
        </td>
        <td>
          <div class="action-buttons">
            <button class="action-btn">|<</button>
            <button class="action-btn primary">签到</button>
            <button class="action-btn">余额</button>
            <button class="action-btn">历史</button>
            <button class="action-btn">编辑</button>
            <button class="action-btn danger">删除</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');

  tbody.innerHTML = rows;
}

function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function truncate(str, len) {
  if (!str) return '';
  if (str.length <= len) return str;
  return str.slice(0, len) + '...';
}

async function init() {
  const data = await loadData();
  if (!data) {
    document.getElementById('accountTbody').innerHTML =
      '<tr><td colspan="7" class="loading">数据加载失败，请确认签到脚本已运行并生成 data/latest.json</td></tr>';
    return;
  }
  renderSummary(data.summary);
  renderAccountList(data.accounts, data.timestamp);
}

document.addEventListener('DOMContentLoaded', init);
