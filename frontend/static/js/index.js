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
    grid.innerHTML = themes.map(t => `
      <a class="topic-card" href="/content/${t.theme_file}" target="_blank">
        <span class="card-icon">${t.icon || '🚀'}</span>
        <h3>${t.title}</h3>
        <p>${t.description || ''}</p>
        ${t.tags && t.tags.length ? `
        <div class="card-tags">
          ${t.tags.map(tag => `<span class="card-tag">${tag.trim()}</span>`).join('')}
        </div>` : ''}
        <div class="card-meta">
          <span>${t.presentation_count || 0} 份演示文稿</span>
        </div>
      </a>
    `).join('');
  } catch (e) {
    grid.innerHTML = '<div class="empty-state"><span class="icon">⚠️</span>加载失败，请稍后重试</div>';
  }
}

document.addEventListener('DOMContentLoaded', loadThemes);

// Auto-refresh every 10 seconds
setInterval(loadThemes, 10000);
