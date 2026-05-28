// index.js — entry page dynamic rendering
async function loadThemes() {
  const grid = document.getElementById('theme-grid');
  try {
    const res = await fetch('/api/themes/public');
    if (!res.ok) { grid.innerHTML = '<div class="empty-state"><span class="icon">⚠️</span>服务暂不可用</div>'; return; }
    const themes = await res.json();
    if (themes.length === 0) {
      grid.innerHTML = '<div class="empty-state"><span class="icon">🔒</span>暂无公开主题</div>';
      return;
    }
    grid.innerHTML = themes.map(t => {
      if (!t.accessible) {
        return `
      <div class="topic-card topic-card-locked" title="此主题暂未开放，敬请期待">
        <span class="card-icon">🔒</span>
        <h3>${t.title}</h3>
        <p>内容暂未开放，敬请期待</p>
        ${t.tags && t.tags.length ? `
        <div class="card-tags">
          ${t.tags.map(tag => `<span class="card-tag">${tag.trim()}</span>`).join('')}
        </div>` : ''}
      </div>`;
      }
      const iconHtml = t.logo_url
        ? `<div class="card-logo-wrap" style="${t.logo_bg ? 'background:' + t.logo_bg : ''}"><img class="card-logo" src="${t.logo_url}" alt="" loading="lazy"></div>`
        : `<span class="card-icon">${t.icon || '🚀'}</span>`;
      return `
      <a class="topic-card" href="${t.entry_url}" target="_blank">
        ${iconHtml}
        <h3>${t.title}</h3>
        <p>${t.description || ''}</p>
        ${t.tags && t.tags.length ? `
        <div class="card-tags">
          ${t.tags.map(tag => `<span class="card-tag">${tag.trim()}</span>`).join('')}
        </div>` : ''}
        <div class="card-meta">
          <span>${t.presentation_count || 0} 份演示文稿</span>
        </div>
      </a>`;
    }).join('');
  } catch (e) {
    grid.innerHTML = '<div class="empty-state"><span class="icon">⚠️</span>加载失败，请稍后重试</div>';
  }
}

async function loadPublicContent() {
  const grid = document.getElementById('content-grid');
  try {
    const res = await fetch('/api/public-content');
    if (!res.ok) { grid.innerHTML = '<div class="empty-state"><span class="icon">⚠️</span>服务暂不可用</div>'; return; }
    const files = await res.json();
    if (files.length === 0) {
      grid.innerHTML = '<div class="empty-state"><span class="icon">🔒</span>暂无公开内容</div>';
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
      html += `
      <div class="content-folder">
        <div class="folder-header" onclick="toggleHomeFolder(this)">
          <span class="folder-arrow">▶</span>
          <span class="folder-name">${folder}</span>
          <span class="folder-count">${items.length} 个文件</span>
        </div>
        <div class="folder-items">
      `;
      for (const f of items) {
        html += `
          <div class="content-item">
            <code>${f.path}</code>
            ${f.theme_title ? `<span class="content-theme" style="color:var(--text-muted);font-size:.7rem;margin-left:8px">${f.theme_title}</span>` : ''}
            <a class="btn btn-sm" href="/content/${f.path}" target="_blank">查看</a>
          </div>
        `;
      }
      html += '</div></div>';
    }
    if (noFolder.length > 0) {
      html += '<div class="content-folder"><div class="folder-header" onclick="toggleHomeFolder(this)">';
      html += '<span class="folder-arrow">▶</span><span class="folder-name">其他</span>';
      html += '</div><div class="folder-items">';
      for (const f of noFolder) {
        html += `
          <div class="content-item">
            <code>${f.path}</code>
            ${f.theme_title ? `<span class="content-theme" style="color:var(--text-muted);font-size:.7rem;margin-left:8px">${f.theme_title}</span>` : ''}
            <a class="btn btn-sm" href="/content/${f.path}" target="_blank">查看</a>
          </div>
        `;
      }
      html += '</div></div>';
    }
    grid.innerHTML = html;
  } catch (e) {
    grid.innerHTML = '<div class="empty-state"><span class="icon">⚠️</span>加载失败，请稍后重试</div>';
  }
}

function toggleHomeFolder(header) {
  const group = header.closest('.content-folder');
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

function switchHomeTab(tab) {
  document.querySelectorAll('.home-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector(`.home-tab-btn[data-tab="${tab}"]`).classList.add('active');
  document.getElementById('home-tab-themes').style.display = tab === 'themes' ? 'block' : 'none';
  document.getElementById('home-tab-content').style.display = tab === 'content' ? 'block' : 'none';
  if (tab === 'content') loadPublicContent();
}

// Tab click handlers
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.home-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchHomeTab(btn.dataset.tab));
  });
  loadThemes();
});

// Auto-refresh every 10 seconds
setInterval(() => {
  const active = document.querySelector('.home-tab-btn.active')?.dataset.tab;
  if (active === 'themes') loadThemes();
}, 10000);
