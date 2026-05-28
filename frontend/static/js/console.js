// console.js — admin console page logic

async function loadConsole() {
  const user = await checkAuth();
  if (!user) { window.location.href = '/login'; return; }
  document.getElementById('user-info').textContent = `${user.username} (${user.role})`;
  loadThemes();
  loadShares();
}

function switchTab(name) {
  document.querySelectorAll('.tab-panel').forEach(p => p.style.display = 'none');
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById('tab-' + name).style.display = 'block';
  document.getElementById('tab-' + name + '-btn').classList.add('active');

  if (name === 'content') loadContentRules();
  if (name === 'audit') loadAudit();
  if (name === 'themes') loadThemes();
  if (name === 'shares') loadShares();
}

// ---- Themes ----
async function loadThemes() {
  try {
    const res = await fetch('/api/themes', { credentials: 'same-origin' });
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
          <label class="toggle">
            <input type="checkbox" ${t.accessible ? 'checked' : ''} onchange="toggleAccessible(${t.id})">
            <span class="slider"></span>
          </label>
        </td>
        <td>
          <button class="btn" onclick="editTheme(${t.id}, '${(t.title || '').replace(/'/g, "\\'")}', '${(t.description || '').replace(/'/g, "\\'")}', '${t.icon || ''}', '${t.logo_url || ''}', '${t.logo_bg || ''}')">编辑</button>
        </td>
        <td>
          <button class="btn" onclick="duplicateTheme(${t.id})">复制</button>
          <button class="btn" onclick="showCreateShare(${t.id}, '${t.title.replace(/'/g, "\\'")}')">分享</button>
          ${t.is_copy ? `<button class="btn btn-danger" onclick="deleteTheme(${t.id}, '${t.title.replace(/'/g, "\\'")}')">删除</button>` : ''}
        </td>
      </tr>
    `).join('');
  } catch (e) {
    document.getElementById('themes-body').innerHTML = '<tr><td colspan="4" style="color:var(--danger)">加载失败</td></tr>';
  }
}

async function toggleVisibility(id) {
  const res = await fetch(`/api/themes/${id}/visibility`, { method: 'PATCH', credentials: 'same-origin' });
  if (res.ok) loadThemes();
}

async function toggleAccessible(id) {
  const res = await fetch(`/api/themes/${id}/accessible`, { method: 'PATCH', credentials: 'same-origin' });
  if (res.ok) loadThemes();
}

async function rescanThemes() {
  showToast('正在从 git 拉取最新内容...');
  const res = await fetch('/api/themes/rescan', { method: 'POST', credentials: 'same-origin' });
  if (res.ok) {
    const data = await res.json();
    if (data.git_pull) {
      console.log('[git pull]', data.git_pull);
    }
    showToast('内容已更新');
    loadThemes();
  } else {
    showToast('拉取失败');
  }
}

// ---- Shares ----
async function loadShares() {
  try {
    const res = await fetch('/api/shares', { credentials: 'same-origin' });
    if (!res.ok) return;
    const shares = await res.json();
    const tbody = document.getElementById('shares-body');
    if (shares.length === 0) {
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">暂无分享链接</td></tr>';
      return;
    }
    tbody.innerHTML = shares.map(s => {
      const fullToken = s.token_full || '';
      return `
      <tr>
        <td>${s.theme_title}</td>
        <td><code style="color:var(--primary)">${s.token}</code></td>
        <td>${s.has_password ? `<code style="color:var(--success);margin-right:4px">${s.password}</code>` : '<span style="color:var(--text-muted)">无</span>'}</td>
        <td>
          <label class="toggle" title="允许访问内容文件">
            <input type="checkbox" ${s.allow_content ? 'checked' : ''} onchange="toggleShareContent(${s.id})">
            <span class="slider"></span>
          </label>
        </td>
        <td>
          <button class="btn" onclick="openShareFileRules(${s.id}, '${s.theme_title.replace(/'/g, "\\'")}')">文件权限</button>
        </td>
        <td style="font-size:.75rem;color:var(--text-muted)">${s.expires_at ? new Date(s.expires_at).toLocaleDateString() : '永久'}</td>
        <td>
          <button class="btn" onclick="copyShareLink('/s/${fullToken}')">复制</button>
          ${s.active ? `<button class="btn btn-danger" onclick="revokeShare(${s.id})">撤销</button>` : '<span style="color:var(--text-muted);margin-right:8px">已撤销</span>'}<button class="btn btn-danger" onclick="deleteShare(${s.id})">删除</button>
        </td>
      </tr>
      `;
    }).join('');
  } catch (e) {}
}

async function toggleShareContent(id) {
  await fetch(`/api/shares/${id}/content`, { method: 'PATCH', credentials: 'same-origin' });
  loadShares();
}

async function revokeShare(id) {
  await fetch(`/api/shares/${id}`, { method: 'DELETE', credentials: 'same-origin' });
  loadShares();
}

async function deleteShare(id) {
  if (!confirm('确定要删除此分享链接吗？删除后无法恢复。')) return;
  const res = await fetch(`/api/shares/${id}/delete`, {
    method: 'DELETE', credentials: 'same-origin'
  });
  if (res.ok) {
    showToast('分享链接已删除');
    loadShares();
  } else {
    showToast('删除失败');
  }
}

function copyShareLink(url) {
  const fullUrl = window.location.origin + url;
  navigator.clipboard.writeText(fullUrl).then(() => {
    showToast('已复制链接: ' + fullUrl);
  }).catch(() => {
    showToast('复制链接失败，请手动复制');
  });
}

function showToast(msg) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.remove('show'), 3000);
}

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
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ theme_id: currentShareThemeId, password, expires_days: expiresDays })
  });
  if (res.ok) {
    const data = await res.json();
    const url = window.location.origin + data.url;
    hideShareModal();
    loadShares();
    navigator.clipboard.writeText(url).then(() => {
      showToast('分享链接已创建并复制: ' + url);
    }).catch(() => {
      showToast('分享链接已创建: ' + url);
    });
  } else {
    const err = await res.json().catch(() => ({}));
    showToast('创建失败: ' + (err.detail || '未知错误'));
  }
}

// ---- Content Rules ----
async function loadContentRules() {
  try {
    const res = await fetch('/api/content-rules', { credentials: 'same-origin' });
    if (!res.ok) return;
    const rules = await res.json();
    const container = document.getElementById('content-rules-list');
    if (rules.length === 0) {
      container.innerHTML = '<p style="color:var(--text-muted)">暂无内容文件</p>';
      return;
    }
    // Group by top-level folder
    const groups = {};
    const noFolder = [];
    for (const r of rules) {
      const parts = r.path.split('/');
      if (parts.length > 1) {
        const folder = parts[0];
        if (!groups[folder]) groups[folder] = [];
        groups[folder].push(r);
      } else {
        noFolder.push(r);
      }
    }
    let html = '';
    const folderNames = Object.keys(groups).sort();
    for (const folder of folderNames) {
      const items = groups[folder];
      const pubCount = items.filter(r => r.public).length;
      html += `
      <div class="folder-group">
        <div class="folder-header" onclick="toggleFolder(this)">
          <span class="folder-arrow">▶</span>
          <span class="folder-name">${folder}</span>
          <span class="folder-count">${pubCount}/${items.length}</span>
          <label class="toggle" onclick="event.stopPropagation()" style="flex-shrink:0;margin-left:auto">
            <input type="checkbox" ${pubCount === items.length ? 'checked' : ''} onchange="folderToggle('${folder}', this.checked)">
            <span class="slider"></span>
          </label>
        </div>
        <div class="folder-items">
      `;
      for (const r of items) {
        html += renderRuleItem(r);
      }
      html += '</div></div>';
    }
    // Files without a folder (root-level)
    if (noFolder.length > 0) {
      html += '<div class="folder-group">';
      html += `<div class="folder-header" onclick="toggleFolder(this)">
        <span class="folder-arrow">▶</span>
        <span class="folder-name">其他</span>
        <span class="folder-count">${noFolder.filter(r => r.public).length}/${noFolder.length}</span>
      </div><div class="folder-items">`;
      for (const r of noFolder) {
        html += renderRuleItem(r);
      }
      html += '</div></div>';
    }
    container.innerHTML = html;
  } catch (e) {
    document.getElementById('content-rules-list').innerHTML = '<p style="color:var(--danger)">加载失败</p>';
  }
}

function renderRuleItem(r) {
  const sourceTag = r.has_rule
    ? '<span style="color:var(--primary);font-size:.65rem;margin-left:6px">已覆盖</span>'
    : `<span style="color:var(--text-muted);font-size:.65rem;margin-left:6px">继承自「${r.theme_title || '未知'}」${r.theme_visible ? '(可见)' : '(隐藏)'}</span>`;
  const copyBtn = r.public
    ? `<button class="btn" style="font-size:.7rem;padding:2px 8px;flex-shrink:0;margin-left:8px" onclick="copyContentLink('${r.path.replace(/'/g, "\\'")}')">复制链接</button>`
    : '';
  return `
    <div class="rule-item" data-path="${r.path}" data-has-rule="${r.has_rule}">
      <code>${r.path}</code>
      ${sourceTag}
      <span class="badge ${r.public ? 'badge-public' : 'badge-hidden'}">${r.public ? '可访问' : '不可访问'}</span>
      ${copyBtn}
      <label class="toggle" style="flex-shrink:0">
        <input type="checkbox" ${r.public ? 'checked' : ''} onchange="toggleContentRule(${r.id || 0}, '${r.path.replace(/'/g, "\\'")}')">
        <span class="slider"></span>
      </label>
    </div>
  `;
}

function toggleFolder(header) {
  const group = header.closest('.folder-group');
  const items = group.querySelector('.folder-items');
  const arrow = header.querySelector('.folder-arrow');
  if (items.style.display === 'block') {
    items.style.display = 'none';
    arrow.style.transform = 'rotate(0deg)';
  } else {
    items.style.display = 'block';
    arrow.style.transform = 'rotate(90deg)';
  }
}

async function folderToggle(folder, isPublic) {
  const group = document.querySelectorAll(`.folder-group .folder-name`);
  let targetHeader = null;
  for (const h of group) {
    if (h.textContent === folder) { targetHeader = h; break; }
  }
  const groupEl = targetHeader?.closest('.folder-group');
  if (!groupEl) return;
  const items = groupEl.querySelectorAll('.rule-item');
  for (const item of items) {
    const path = item.dataset.path;
    const input = item.querySelector('input');
    if (!input) continue;
    const ruleIdMatch = input.getAttribute('onchange')?.match(/toggleContentRule\((\d+)/);
    const ruleId = ruleIdMatch ? ruleIdMatch[1] : '0';
    if (input.checked !== isPublic) {
      input.checked = isPublic;
      // Fire toggleContentRule
      if (ruleId !== '0') {
        toggleContentRule(parseInt(ruleId), path);
      } else {
        const res = await fetch('/api/content-rules', {
          method: 'POST', credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path, public: isPublic })
        });
        if (res.ok) { /* will reload below */ }
      }
    }
  }
  setTimeout(loadContentRules, 500);
}

function copyContentLink(path) {
  const fullUrl = window.location.origin + '/content/' + path;
  navigator.clipboard.writeText(fullUrl).then(() => {
    showToast('已复制链接: ' + fullUrl);
  }).catch(() => {
    showToast('复制链接失败，请手动复制');
  });
}

async function pullAndLoadContentRules() {
  showToast('正在从 git 拉取最新内容...');
  const res = await fetch('/api/themes/rescan', { method: 'POST', credentials: 'same-origin' });
  if (res.ok) {
    showToast('内容已更新');
    loadContentRules();
  } else {
    showToast('拉取失败');
  }
}

async function copyAllContentLinks() {
  const res = await fetch('/api/content-rules', { credentials: 'same-origin' });
  if (!res.ok) return;
  const rules = await res.json();
  const publicRules = rules.filter(r => r.public);
  if (publicRules.length === 0) {
    showToast('没有公开的文件可复制');
    return;
  }
  const links = publicRules.map(r => window.location.origin + '/content/' + r.path).join('\n');
  navigator.clipboard.writeText(links).then(() => {
    showToast(`已复制 ${publicRules.length} 个文件的公开访问链接`);
  }).catch(() => {
    showToast('复制链接失败，请手动复制');
  });
}

async function toggleContentRule(id, path) {
  const el = document.querySelector(`.rule-item[data-path="${CSS.escape(path)}"]`);
  if (!el) return;
  const isPublic = el.querySelector('input').checked;
  if (!id) {
    // Rule doesn't exist yet, create it first
    const res = await fetch('/api/content-rules', {
      method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ path, public: isPublic })
    });
    if (res.ok) loadContentRules();
    return;
  }
  const res = await fetch(`/api/content-rules/${id}`, {
    method: 'PATCH', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ public: isPublic })
  });
  if (res.ok) {
    const badge = el.querySelector('.badge');
    badge.className = `badge ${isPublic ? 'badge-public' : 'badge-hidden'}`;
    badge.textContent = isPublic ? '公开' : '隐藏';
  }
}

async function bulkToggle(public) {
  if (!confirm(`确定要${public ? '全部公开' : '全部隐藏'}所有文件吗？`)) return;
  const res = await fetch('/api/content-rules/bulk', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ public })
  });
  if (res.ok) {
    const data = await res.json();
    showToast(`已更新 ${data.changed} 个文件`);
    loadContentRules();
  }
}

// ---- Theme Edit ----
let currentEditThemeId = null;
let pendingLogoFile = null;
let pendingLogoBg = '';
const EMOJI_LIST = ['🚀','🔥','💡','🎯','📊','🧠','⚡','🔮','🎨','🛠','📦','🌍','💻','🔐','📱','🎵','🎬','📝','🏆','🚀','✨','🌟','💎','🎪','🏅','🎭','📡','🧩','🌈','🎁'];

function editTheme(id, title, description, icon, logoUrl, logoBg) {
  currentEditThemeId = id;
  document.getElementById('theme-edit-title').value = title;
  document.getElementById('theme-edit-description').value = description;
  pendingLogoFile = logoUrl || null;
  pendingLogoBg = logoBg || '';
  renderLogoPreview(logoUrl, icon);
  renderEmojiPicker(icon);
  renderLogoBgPicker(logoBg);
  document.getElementById('theme-edit-modal').classList.add('active');
}

function renderLogoBgPicker(bg) {
  const resolved = bg || '#141a27';
  pendingLogoBg = resolved;
  document.getElementById('logo-bg-picker').value = resolved;
  document.getElementById('logo-bg-text').value = resolved;
  console.log('[logoBg] editTheme received:', JSON.stringify(bg), 'resolved to:', resolved);
}

function clearLogoBg() {
  pendingLogoBg = '#141a27';
  document.getElementById('logo-bg-text').value = '';
  document.getElementById('logo-bg-picker').value = '#141a27';
}

function onLogoBgChange(val) {
  pendingLogoBg = val;
  document.getElementById('logo-bg-text').value = val;
}
document.getElementById('logo-bg-picker').addEventListener('input', function() { onLogoBgChange(this.value); });
document.getElementById('logo-bg-picker').addEventListener('change', function() { onLogoBgChange(this.value); });
document.getElementById('logo-bg-text').addEventListener('input', function() {
  pendingLogoBg = this.value;
  if (/^#[0-9a-fA-F]{6}$/.test(this.value)) {
    document.getElementById('logo-bg-picker').value = this.value;
  }
});

function renderLogoPreview(logoUrl, icon) {
  const area = document.getElementById('logo-preview-area');
  if (logoUrl) {
    area.innerHTML = `<img src="${logoUrl}" alt="" style="${pendingLogoBg ? 'background:' + pendingLogoBg : ''}">`;
  } else if (icon) {
    area.innerHTML = icon;
  } else {
    area.innerHTML = '🚀';
  }
}

function renderEmojiPicker(currentIcon) {
  const picker = document.getElementById('emoji-picker');
  picker.innerHTML = EMOJI_LIST.map(e => {
    const sel = (e === currentIcon && !currentIcon.startsWith('logo:')) ? ' selected' : '';
    return `<div class="emoji-option${sel}" onclick="selectEmoji('${e}')">${e}</div>`;
  }).join('');
}

function selectEmoji(emoji) {
  pendingLogoFile = null;
  renderLogoPreview(null, emoji);
  renderEmojiPicker(emoji);
}

async function uploadLogo() {
  const input = document.getElementById('logo-file-input');
  const file = input.files[0];
  if (!file || !currentEditThemeId) return;
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`/api/themes/${currentEditThemeId}/logo`, {
    method: 'POST', credentials: 'same-origin', body: form
  });
  if (res.ok) {
    const data = await res.json();
    pendingLogoFile = data.url;
    renderLogoPreview(data.url, null);
    renderEmojiPicker('');
    input.value = '';
    showToast('Logo 已上传');
  } else {
    const err = await res.json().catch(() => ({}));
    showToast('上传失败: ' + (err.detail || '未知错误'));
  }
}

async function removeLogo() {
  if (!currentEditThemeId) return;
  const res = await fetch(`/api/themes/${currentEditThemeId}/logo`, {
    method: 'DELETE', credentials: 'same-origin'
  });
  if (res.ok) {
    pendingLogoFile = null;
    renderLogoPreview(null, null);
    renderEmojiPicker('');
    showToast('Logo 已删除');
  } else {
    showToast('删除失败');
  }
}

function hideThemeEditModal() {
  document.getElementById('theme-edit-modal').classList.remove('active');
  currentEditThemeId = null;
  pendingLogoFile = null;
  pendingLogoBg = '';
}

async function saveThemeEdit() {
  if (!currentEditThemeId) return;
  const title = document.getElementById('theme-edit-title').value;
  const description = document.getElementById('theme-edit-description').value;
  const preview = document.getElementById('logo-preview-area');
  const img = preview.querySelector('img');
  let icon = '';
  if (img) {
    icon = `logo:${img.src.split('/').pop()}`;
  } else {
    icon = preview.textContent.trim();
  }
  const res = await fetch(`/api/themes/${currentEditThemeId}`, {
    method: 'PATCH', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, description, icon, logo_bg: pendingLogoBg })
  });
  if (res.ok) {
    hideThemeEditModal();
    showToast('主题已更新');
    loadThemes();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast('更新失败: ' + (err.detail || '未知错误'));
  }
}

async function duplicateTheme(id) {
  if (!confirm('确定要复制此主题吗？复制后的主题将指向同一个文件，但可独立编辑卡片信息。')) return;
  const res = await fetch(`/api/themes/${id}/duplicate`, {
    method: 'POST', credentials: 'same-origin'
  });
  if (res.ok) {
    const data = await res.json();
    showToast(`已复制主题: ${data.title} (slug: ${data.slug})`);
    loadThemes();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast('复制失败: ' + (err.detail || '未知错误'));
  }
}

async function deleteTheme(id, title) {
  if (!confirm(`确定要删除主题「${title}」吗？此操作仅删除数据库记录，不影响实际文件。`)) return;
  const res = await fetch(`/api/themes/${id}`, {
    method: 'DELETE', credentials: 'same-origin'
  });
  if (res.ok) {
    showToast(`已删除主题: ${title}`);
    loadThemes();
  } else {
    const err = await res.json().catch(() => ({}));
    showToast('删除失败: ' + (err.detail || '未知错误'));
  }
}

// ---- Audit Log ----
async function loadAudit() {
  try {
    const res = await fetch('/api/audit?limit=20', { credentials: 'same-origin' });
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
        ${l.ip_address ? `<span style="color:var(--success);margin-left:8px;font-size:.75rem">🌐 ${l.ip_address}</span>` : ''}
      </div>
    `).join('');
  } catch (e) {}
}

async function cleanupAudit() {
  const dateInput = document.getElementById('audit-cleanup-date');
  if (!dateInput.value) {
    showToast('请先选择一个日期');
    return;
  }
  if (!confirm(`确定要删除 ${dateInput.value} 之前的所有审计日志吗？`)) return;
  const res = await fetch('/api/audit/cleanup', {
    method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ before_date: dateInput.value + 'T00:00:00' })
  });
  if (res.ok) {
    const data = await res.json();
    showToast(`已清理 ${data.deleted} 条日志`);
    loadAudit();
  } else {
    showToast('清理失败');
  }
}

// ---- Share File Rules ----
let currentShareFileRulesShareId = null;

async function openShareFileRules(shareId, themeTitle) {
  currentShareFileRulesShareId = shareId;
  document.getElementById('sfr-modal-title').textContent = `文件权限 - ${themeTitle}`;
  document.getElementById('share-file-rules-modal').classList.add('active');
  await loadShareFileRules(shareId);
}

function hideShareFileRulesModal() {
  document.getElementById('share-file-rules-modal').classList.remove('active');
  currentShareFileRulesShareId = null;
}

async function loadShareFileRules(shareId) {
  const res = await fetch(`/api/shares/${shareId}/files`, { credentials: 'same-origin' });
  if (!res.ok) return;
  const files = await res.json();
  const container = document.getElementById('sfr-file-list');
  if (files.length === 0) {
    container.innerHTML = '<p style="color:var(--text-muted)">此主题下没有文件</p>';
    return;
  }
  // Group by top-level folder
  const groups = {};
  const noFolder = [];
  for (const f of files) {
    const parts = f.path.split('/');
    if (parts.length > 1) {
      const folder = parts[0];
      if (!groups[folder]) groups[folder] = [];
      groups[folder].push(f);
    } else {
      noFolder.push(f);
    }
  }
  let html = '';
  for (const folder of Object.keys(groups).sort()) {
    const items = groups[folder];
    const pubCount = items.filter(f => f.public).length;
    html += `
    <div class="folder-group">
      <div class="folder-header" onclick="toggleFolder(this)">
        <span class="folder-arrow">▶</span>
        <span class="folder-name">${folder}</span>
        <span class="folder-count">${pubCount}/${items.length}</span>
      </div>
      <div class="folder-items">
    `;
    for (const f of items) {
      html += renderShareFileItem(shareId, f);
    }
    html += '</div></div>';
  }
  if (noFolder.length > 0) {
    html += '<div class="folder-group"><div class="folder-header" onclick="toggleFolder(this)">';
    html += '<span class="folder-arrow">▶</span><span class="folder-name">其他</span>';
    html += '</div><div class="folder-items">';
    for (const f of noFolder) {
      html += renderShareFileItem(shareId, f);
    }
    html += '</div></div>';
  }
  container.innerHTML = html;
}

function renderShareFileItem(shareId, f) {
  const sourceLabel = f.source === 'share_rule'
    ? '<span style="color:var(--accent);font-size:.65rem;margin-left:6px">分享规则</span>'
    : f.source === 'global_rule'
    ? '<span style="color:var(--primary);font-size:.65rem;margin-left:6px">全局规则</span>'
    : `<span style="color:var(--text-muted);font-size:.65rem;margin-left:6px">继承</span>`;
  return `
    <div class="rule-item" data-path="${f.path}">
      <code>${f.path}</code>
      ${sourceLabel}
      <span class="badge ${f.public ? 'badge-public' : 'badge-hidden'}">${f.public ? '可访问' : '不可访问'}</span>
      <label class="toggle" style="flex-shrink:0">
        <input type="checkbox" ${f.public ? 'checked' : ''}
          onchange="toggleShareFileRule(${shareId}, '${f.path.replace(/'/g, "\\'")}', ${f.share_rule_id || 0})">
        <span class="slider"></span>
      </label>
    </div>
  `;
}

async function toggleShareFileRule(shareId, path, existingRuleId) {
  const el = document.querySelector(`#sfr-file-list .rule-item[data-path="${CSS.escape(path)}"]`);
  if (!el) return;
  const isPublic = el.querySelector('input').checked;
  const res = await fetch(`/api/shares/${shareId}/files/${encodeURIComponent(path)}`, {
    method: 'PATCH', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ public: isPublic })
  });
  if (res.ok) {
    const badge = el.querySelector('.badge');
    badge.className = `badge ${isPublic ? 'badge-public' : 'badge-hidden'}`;
    badge.textContent = isPublic ? '可访问' : '不可访问';
    const sourceSpan = el.querySelector('span[style*="margin-left"]');
    if (sourceSpan) {
      sourceSpan.outerHTML = '<span style="color:var(--accent);font-size:.65rem;margin-left:6px">分享规则</span>';
    }
  } else {
    showToast('更新失败');
    await loadShareFileRules(shareId);
  }
}

document.addEventListener('DOMContentLoaded', loadConsole);
