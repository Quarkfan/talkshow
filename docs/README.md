# Talkshow — 分享导航系统

> 一个面向内部分享的内容管理系统 + 导航门户，v1.0.0

## 项目概览

Talkshow 是一套完整的分享导航系统，用于管理、发布和追踪对内对外分享的内容（演示文稿、文档等）。它提供三层访问模型：

1. **主题入口页** — `/t/{slug}` — 匿名访问，面向特定主题的观众
2. **分享链接** — `/s/{token}` — 可选密码/过期，带文件级权限覆盖
3. **首页导航** — `/` — 所有公开主题的统一入口

### 核心能力

- 主题管理：可见性、可访问性、Logo、Emoji 图标
- 内容权限：文件级公开/隐藏控制，支持全局规则和分享级别覆盖
- 分享管理：密码保护、过期控制、文件级权限定制
- 审计日志：所有管理操作可追溯
- 自动备份：SQLite 数据库自动同步到 GitHub
- 内容隔离：通过 Docker named volume 与本地机器隔离，从 git 远端拉取

## 技术栈

| 层面 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + SQLite (WAL mode) |
| 前端 | 纯 HTML + Vanilla JS + CSS (无框架) |
| 部署 | Docker Compose (2 services) |
| 备份 | git (SSH) 自动 commit + force push |
| 认证 | Session-based cookie (SessionMiddleware) |

## 目录结构

```
talkshow/
├── backend/                    # 后端 Python
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口，所有路由注册 + 页面路由
│   ├── config.py               # 环境变量配置 (CONTENT_DIR, SECRET_KEY 等)
│   ├── database.py             # SQLAlchemy engine + session
│   ├── models.py               # 数据模型 (User, Theme, ShareLink, AuditLog, ContentRule, ShareFileRule)
│   ├── auth.py                 # 认证中间件 (require_auth, require_admin)
│   ├── utils.py                # 工具函数 (resolve_file_theme, scan_files)
│   ├── init_db.py              # 内容目录扫描 → 主题表初始化
│   ├── backup.py               # SQLite 自动备份到 GitHub (debounce + git amend)
│   └── routes/                 # API 路由
│       ├── __init__.py
│       ├── auth.py             # POST /api/login, GET /api/me, POST /api/logout
│       ├── themes.py           # 主题 CRUD + Logo 上传 + 可见性/可访问性切换
│       ├── shares.py           # 分享链接 CRUD + 验证
│       ├── audit.py            # 审计日志查询 + 清理
│       ├── content_rules.py    # 全局内容权限 (需要 auth)
│       └── share_file_rules.py # 分享文件权限覆盖 (需要 auth)
│
├── frontend/                   # 前端静态资源
│   ├── index.html              # 首页导航 (主题 + 内容 双标签)
│   ├── console.html            # 管理控制台 (主题/内容权限/分享/审计)
│   ├── login.html              # 登录页
│   ├── blocked.html            # 禁止访问页
│   ├── locked.html             # 内容锁定页
│   └── static/
│       ├── css/style.css       # 全局样式 (暗色主题)
│       └── js/
│           ├── auth.js         # 认证逻辑 (checkAuth, login, logout)
│           ├── index.js        # 首页逻辑 (主题加载 + 内容标签切换)
│           └── console.js      # 控制台逻辑 (所有管理功能)
│
├── data/                       # 本地数据 (mount 到容器 /app/data)
│   ├── talkshow.db             # SQLite 数据库 (WAL mode)
│   └── logos/                  # 上传的主题 Logo 图片
│
├── docs/                       # 项目文档 (本目录)
│   ├── README.md               # 本文件 — 项目总览
│   └── STATUS.md               # 当前进度 + 待办事项
│
├── Dockerfile                  # 后端服务镜像 (含 git + openssh)
├── entrypoint.sh               # 启动脚本 (git clone/pull content)
├── docker-compose.yml          # 双服务编排 (platform + ai-tool-finder)
├── requirements.txt            # Python 依赖
├── .env                        # 环境变量 (gitignored)
└── .env.example                # 环境变量模板
```

## 数据模型

```
users
  ├── id, username, password_hash, role (admin)
  └── ← AuditLog.user_id, ShareLink.created_by

themes
  ├── id, slug, title, description, theme_file
  ├── icon (emoji 或 "logo:文件名"), logo_bg
  ├── visible (主页显示), accessible (内容可访问性)
  ├── is_copy (可删除), presentation_count
  └── ← ContentRule.theme_id, ShareLink.theme_id

content_rules (全局文件权限)
  ├── id, path (unique), public (bool)
  └── theme_id (冗余字段，方便关联)

share_links
  ├── id, theme_id, token, password, expires_at
  ├── active, allow_content (第三层内容访问开关)
  └── created_by, created_at

share_file_rules (分享文件权限覆盖)
  ├── id, share_id, path, public (bool)
  └── (share_id, path) unique

audit_logs
  ├── id, user_id, action, detail (JSON string), ip_address
  └── created_at (indexed)
```

## 访问控制逻辑

### 权限优先级 (从高到低)

1. **ContentRule** (全局文件规则) — `public=False` 直接拒绝，最高优先级
2. **ShareFileRule** (分享文件规则) — 仅对 `/s/{token}` 路径生效
3. **Theme.accessible** (主题可访问性) — 文件继承所属主题的 accessible
4. **ShareLink.allow_content** — 控制是否允许通过分享链接访问第三层内容

### 匿名用户访问 `/content/{path}` 的流程

```
请求 /content/some/path
  → ContentRule(public=False)? → /blocked
  → 属于某个 Theme?
    → Theme.accessible=False? → /blocked
    → 允许访问
  → 不属于任何 Theme?
    → 至少一个 Theme.accessible=True? → 允许
    → 否则 → /blocked
```

## 备份系统

**文件**: `backend/backup.py`

- 触发：每次非日志变更（主题/分享/权限操作）后调用 `schedule_backup()`
- 机制：30 秒 debounce → 复制 DB → `git commit --amend` → `git push --force`
- 历史：保留一份 `.bak.prev` 上一代备份
- 安全：`_ready` 标志确保 git 配置完成后才执行备份
- SSH：使用 `~/.ssh/id_ed25519_github` 密钥，仓库复用 `Quarkfan/talkshow`

## 部署架构

```
                  Docker Compose
        ┌─────────────────────────────────┐
        │                                 │
   :8800│ talkshow-platform               │
   ────►│  FastAPI :8000                  │
        │  /content → content-data vol    │
        │  /app/data → ./data (host)      │
        │  SSH key (ro)                   │
        │                                 │
  :18000│ talkshow-tool-finder            │
   ────►│  AI 工具查找 (独立服务)          │
        │                                 │
        └─────────────────────────────────┘

  content-data: Docker named volume (不与宿主机共享)
  entrypoint.sh: 启动时 git clone/fetch --hard origin/main
```

## 启动与开发

### 首次启动

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 设置 SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD

# 2. 确保 SSH 密钥存在
~/.ssh/id_ed25519_github  # 用于 git clone talkResources

# 3. 启动
docker compose up -d --build

# 4. 访问
# 首页: http://localhost:8800
# 控制台: http://localhost:8800/console
# 登录: http://localhost:8800/login (用 .env 中的 admin 账号)
```

### 开发修改后重建

```bash
docker compose up -d --build
```

### 前端热更新

当前没有热更新。修改后需重建 Docker 镜像。前端 JS/CSS 通过版本查询参数 (`?v=6`) 控制浏览器缓存。

## Git 仓库

- 主仓库: `git@github.com:Quarkfan/talkshow.git` (本项目)
- 内容仓库: `git@github.com:Quarkfan/talkResources.git` (mount 到 `/content`)
- 备份: 推送到主仓库的 `backups/` 目录

## 版本历史

| 版本 | 说明 |
|------|------|
| v1.0.0 | 完整的内容权限管理系统 |
