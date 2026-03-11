function formatTime(isoString) {
  const d = new Date(isoString);
  const now = new Date();
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) {
    return '昨天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  }
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function renderLogs(logs) {
  const el = document.getElementById('logsContainer');
  if (!logs || logs.length === 0) {
    el.innerHTML = '<div class="empty"><div class="empty-icon">📝</div>暂无日志</div>';
    return;
  }
  el.innerHTML = logs.map(log => {
    const details = log.details ? `<div class="log-details">${JSON.stringify(log.details, null, 2)}</div>` : '';
    return `<div class="log-entry ${log.level}">
      <div class="log-header">
        <span class="log-level ${log.level}">${log.level}</span>
        <span class="log-time">${formatTime(log.timestamp)}</span>
      </div>
      <div class="log-message">${log.message}</div>
      ${details}
    </div>`;
  }).join('');
}

function loadLogs() {
  chrome.runtime.sendMessage({ action: 'getLogs' }, (resp) => {
    renderLogs(resp && resp.success ? resp.logs : null);
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadLogs();
  document.getElementById('refreshBtn').addEventListener('click', loadLogs);
  document.getElementById('clearBtn').addEventListener('click', () => {
    if (!confirm('确定清空所有日志？')) return;
    chrome.runtime.sendMessage({ action: 'clearLogs' }, () => loadLogs());
  });
  document.getElementById('backBtn').addEventListener('click', () => { window.location.href = 'popup.html'; });
  setInterval(loadLogs, 5000);
});
