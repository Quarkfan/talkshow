# 项目状态

> 更新日期: 2026-05-28
> 当前版本: v1.0.0

## 已完成

### 核心系统

- [x] FastAPI 后端 + SQLite (WAL mode)
- [x] Session-based 认证 (admin 角色)
- [x] Docker Compose 双服务部署
- [x] 前端暗色主题 UI (无框架，Vanilla JS)

### 主题管理

- [x] 从 git 内容仓库自动扫描主题 (`themes/*.html`)
- [x] 主题可见性切换 (主页是否显示卡片)
- [x] 主题可访问性切换 (内容是否可访问)
- [x] 主题 Logo 上传 (PNG/JPG/SVG/WebP/GIF)
- [x] Emoji 选择器 (30 个预设)
- [x] Logo 背景色设置 (解决透明 PNG 问题)
- [x] 主题复制/删除 (仅允许删除复制的主题)
- [x] 主题信息编辑 (标题、描述、图标)

### 内容权限

- [x] 全局内容规则 API (`/api/content-rules`) — 文件级公开/隐藏
- [x] 按文件夹分组展示 (可折叠，文件夹级别批量切换)
- [x] 继承主题可见性作为默认值
- [x] 公开文件可一键复制访问链接
- [x] 批量公开/隐藏所有文件
- [x] 从 git 远端拉取内容 (main 分支)
- [x] 内容目录与宿主机隔离 (Docker named volume)

### 分享系统

- [x] 分享链接创建 (密码保护、过期时间)
- [x] 分享链接列表、撤销、删除
- [x] 分享链接内容开关 (`allow_content`)
- [x] 分享文件级权限覆盖 (`ShareFileRule`)
- [x] 分享文件权限也按文件夹分组
- [x] 分享密码页面 (简单 HTML 表单)

### 内容服务

- [x] `/content/{path}` — 统一内容代理
- [x] 匿名访问权限检查 (ContentRule → Theme → fallback)
- [x] 管理员直接访问 (session 认证跳过权限检查)
- [x] HTML 注入 `<base>` 标签解决相对链接
- [x] `/t/{slug}` — 主题入口 (匿名)
- [x] `/s/{token}` — 分享入口 (匿名，带密码验证)
- [x] 首页内容标签页 (展示所有公开内容文件)

### 审计与备份

- [x] 审计日志 (所有管理操作记录)
- [x] 审计日志清理 (按日期删除旧记录)
- [x] SQLite 自动备份到 GitHub (debounce 30s)
- [x] `git commit --amend` + `push --force` (单条历史)
- [x] 保留上一代备份 (`.db.prev`)
- [x] `_ready` 标志防止启动时过早备份

### 运维

- [x] 启动脚本 `entrypoint.sh` (git clone/fetch --hard)
- [x] SSH 密钥挂载 (只读)
- [x] 静态文件 no-cache 中间件
- [x] JS/CSS 版本查询参数防缓存

## 待办事项

### 可能的改进 (未排期)

- [ ] 前端热更新 (当前需重建 Docker 镜像)
- [ ] 内容权限支持子文件夹级别 (目前只按一级文件夹分组)
- [ ] 分享内容预览 (缩略图或文件类型图标)
- [ ] 分享链接使用统计 (点击次数、最近访问时间)
- [ ] 多用户支持 (当前只有 admin)
- [ ] 备份版本历史 (当前只保留一代)
- [ ] CI/CD 自动化部署
- [ ] HTTPS / 域名配置
- [ ] 移动端适配优化

### 已知限制

1. **CSS 版本号未更新**: `style.css` 当前版本是 `v=2`，如果修改了 CSS 需要同步更新 `index.html` 和 `console.html` 中的引用
2. **内容拉取只关注 main 分支**: `entrypoint.sh` 中 `git fetch origin main && git reset --hard origin/main`
3. **备份使用 force push**: 会覆盖远端之前的备份提交
4. **SQLite 单文件数据库**: 高并发场景可能需要迁移到 PostgreSQL
5. **Logo 文件大小限制**: 2MB

## 当前数据状态

- 主题数: 2 (1 个原始 + 1 个复制)
- 内容文件数: 32
- ContentRule 记录: 30 (大部分设为 public=False)
- 公开内容: 0 (所有文件均被设为不公开)

## 部署状态

- Docker 容器运行正常
- 端口: `:8800` (platform), `:18000` (ai-tool-finder)
- 内容从 `Quarkfan/talkResources` git 仓库拉取
- SSH 密钥: `~/.ssh/id_ed25519_github`

## 快速上手指南

接手后建议先做以下几步：

1. 阅读 `docs/README.md` 了解架构
2. `docker compose ps` 确认服务运行正常
3. 访问 `http://localhost:8800/console` 登录管理后台
4. 在控制台 → 内容权限 中把文件设为公开，然后去首页内容标签查看效果
5. 修改代码后 `docker compose up -d --build` 重建
