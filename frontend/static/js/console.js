// console.js — admin console page logic

async function loadConsole() {
  const user = await checkAuth();
  if (!user) { window.location.href = '/login'; return; }
  document.getElementById('user-info').textContent = `${user.username} (${user.role})`;

  loadThemes();
  loadShares();
  loadAudit();
}

async function loadThemes() {
  try {
    const res = await fetch('/api/themes');
    if (!res.ok) { window.location.href = '/login'; return; }
    const themes = await res.json();
    const tbody = document.getElementById('themes-body');
    if (themes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">暂无主题，请点击"重新扫描内容"</td></tr>';
      return;
    }
    tbody.innerHTML = themes.map(t => `
      <tr>
        <td><span style="margin-right:6px">${t.icon || '🚀'}</span>${t.title}</td>
        <td style="font-size:.75rem;color:var(--text-muted)">${t.theme_file}</td>
        <td>
          <label class="toggle">
            <input type="checkbox" ${t.visible ? 'checked' : ''} onchange="toggleVisibility(${t.id})">
            <span class="slider"></span>
          </label>
        </td>
        <td>
          <button class="btn" onclick="showCreateShare(${t.id}, '${t.title.replace(/'/g, "\\'")}')">分享</button>
        </td>
      </tr>
    `).join('');
  } catch (e) {
    document.getElementById('themes-body').innerHTML = '<tr><td colspan="4" style="color:var(--danger)">加载失败</td></tr>';
  }
}

async function toggleVisibility(id) {
  await fetch(`/api/themes/${id}/visibility`, { method: 'PATCH' });
}

async function rescanThemes() {
  const res = await fetch('/api/themes/rescan', { method: 'POST' });
  if (res.ok) loadThemes();
}

// Share links
async function loadShares() {
  try {
    const res = await fetch('/api/shares');
    if (!res.ok) return;
    const shares = await res.json();
    const tbody = document.getElementById('shares-body');
    if (shares.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">暂无分享链接</td></tr>';
      return;
    }
    tbody.innerHTML = shares.map(s => `
      <tr>
        <td>${s.theme_title}</td>
        <td><code style="color:var(--primary)">${s.token}</code>${s.has_password ? ' 🔒' : ''}</td>
        <td style="font-size:.75rem;color:var(--text-muted)">${s.expires_at ? new Date(s.expires_at).toLocaleDateString() : '永久'}</td>
        <td>
          <button class="btn" onclick="copyShareLink('/s/${s.token_full || s.token.replace('...', '')}')">复制</button>
          ${s.active ? `<button class="btn btn-danger" onclick="revokeShare(${s.id})">撤销</button>` : '<span style="color:var(--text-muted)">已撤销</span>'}
        </td>
      </tr>
    `).join('');
  } catch (e) {}
}

async function revokeShare(id) {
  await fetch(`/api/shares/${id}`, { method: 'DELETE' });
  loadShares();
}

function copyShareLink(url) {
  navigator.clipboard.writeText(window.location.origin + url);
}

// Modal for creating share links
let currentShareThemeId = null;

function showCreateShare(themeId, themeTitle) {
  currentShareThemeId = themeId;
  document.getElementById('share-theme-label').textContent = `为「${themeTitle}」创建分享链接`;
  document.getElementById('share-modal').classList.add('active');
  document.getElementById('share-pw').value = '';
  document.getElementById('share-days').value = '';
}

function hideShareModal() {
  document.getElementById('share-modal').classList.remove('active');
  currentShareThemeId = null;
}

async function createShare() {
  const password = document.getElementById('share-pw').value || null;
  const expiresDays = parseInt(document.getElementById('share-days').value) || null;

  const res = await fetch('/api/shares', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme_id: currentShareThemeId, password, expires_days: expiresDays })
  });

  if (res.ok) {
    const data = await res.json();
    const url = window.location.origin + data.url + (password ? `?password=${password}` : '');
    navigator.clipboard.writeText(url).then(() => {
      alert('分享链接已复制到剪贴板');
    });
    hideShareModal();
    loadShares();
  } else {
    alert('创建失败');
  }
}

// Audit log
async function loadAudit() {
  try {
    const res = await fetch('/api/audit?limit=20');
    if (!res.ok) return;
    const logs = await res.json();
    const container = document.getElementById('audit-log');
    if (logs.length === 0) {
      container.innerHTML = '<p style="color:var(--text-muted)">暂无审计记录</p>';
      return;
    }
    container.innerHTML = logs.map(l => `
      <div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:.8rem">
        <span style="color:var(--text-muted)">${new Date(l.created_at).toLocaleString()}</span>
        <span style="color:var(--primary);margin-left:8px">${l.action}</span>
        ${l.detail ? `<span style="color:var(--text-secondary);margin-left:8px;font-size:.75rem">${l.detail}</span>` : ''}
      </div>
    `).join('');
  } catch (e) {}
}

// Run on load
document.addEventListener('DOMContentLoaded', loadConsole);
