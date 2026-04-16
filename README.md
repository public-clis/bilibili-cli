# bilibili-cli

[![CI](https://github.com/jackwener/bilibili-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/jackwener/bilibili-cli/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/bilibili_cli.svg)](https://pypi.org/project/bilibili-cli/)
[![Python versions](https://img.shields.io/pypi/pyversions/bilibili_cli.svg)](https://pypi.org/project/bilibili-cli/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](./LICENSE)

A CLI for Bilibili — browse videos, users, favorites from the terminal 📺

[English](#features) | [中文](#功能特性)

## More Projects

- [xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) — Xiaohongshu (小红书) CLI for notes and account workflows
- [twitter-cli](https://github.com/jackwener/twitter-cli) — Twitter/X CLI tooling
- [discord-cli](https://github.com/jackwener/discord-cli) — Discord CLI for local-first chat sync and search
- [tg-cli](https://github.com/jackwener/tg-cli) — Telegram CLI for local-first sync, search, and export

## Features

- 🎬 **Video** — details, subtitles, AI summary, comments, related videos
- 🎵 **Audio** — extract audio and split into ASR-ready WAV segments
- 👤 **User** — profile, video list, following list
- 🔍 **Search** — search users or videos by keyword
- 🔥 **Trending** — hot videos and site-wide ranking
- 📰 **Feed** — dynamic timeline from your follows
- 📂 **Favorites** — browse favorite folders, watch-later, and watch history
- 👍 **Interactions** — like, coin, triple (一键三连)
- 🔐 **Smart auth** — auto-extracts cookies from Chrome/Firefox, or QR code login
- 📊 **Structured output** — major query commands support `--yaml` and `--json`
- 🤖 **Agent-friendly defaults** — non-TTY stdout defaults to YAML; override with `OUTPUT=yaml|json|rich|auto`
- 📦 **Stable envelope** — see [SCHEMA.md](./SCHEMA.md) for `ok/schema_version/data/error`
- 🧱 **Normalized payloads** — command-layer output is normalized instead of leaking raw upstream SDK responses

## Installation

```bash
# Recommended: uv tool (fast, isolated)
uv tool install bilibili-cli

# Or: pipx
pipx install bilibili-cli

# If you need audio extraction support
uv tool install "bilibili-cli[audio]"
# or
pipx install "bilibili-cli[audio]"
```

Upgrade to the latest version:

```bash
uv tool upgrade bilibili-cli
# Or: pipx upgrade bilibili-cli
```

> **Tip:** Upgrade regularly to avoid unexpected errors from outdated API handling.

Or from source:

```bash
git clone git@github.com:jackwener/bilibili-cli.git
cd bilibili-cli
uv sync
```

Run tests in the project environment:

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv run python -m mypy bili_cli
```

If the project directory was moved and stale virtualenv wrappers remain, rerun:

```bash
uv sync --extra dev --reinstall
```

## Usage

```bash
# Login & account
bili status                    # Check login status
bili status --yaml             # Structured auth status
bili login                     # QR code login
bili whoami                    # Detailed profile (level, coins, followers)
bili whoami --yaml             # Structured profile

# Videos
bili video BV1ABcsztEcY                 # Video details
bili video BV1ABcsztEcY --subtitle      # With subtitles (plain text)
bili video BV1ABcsztEcY --subtitle-timeline        # With timeline
bili video BV1ABcsztEcY -st --subtitle-format srt  # Export as SRT
bili video BV1ABcsztEcY --ai            # AI summary
bili video BV1ABcsztEcY --comments      # Top comments
bili video BV1ABcsztEcY --related       # Related videos
bili video BV1ABcsztEcY --yaml          # Agent-friendly YAML
bili video BV1ABcsztEcY --json          # Normalized JSON envelope
bili video BV1ABcsztEcY --subtitle-timeline --comments --json  # Extras in one payload

# Users
bili user 946974                        # UP profile
bili user "影视飓风"                     # Search by name
bili user-videos 946974 --max 20        # Video list

# Discovery
bili hot                                # Trending videos (page 1)
bili hot --page 2 --max 10              # Page 2, top 10
bili rank                               # Site-wide ranking (3-day)
bili rank --day 7 --max 30              # 7-day ranking, top 30
bili search "关键词"                     # Search users
bili search "关键词" --type video --max 5 # Search videos (top 5)
bili search "关键词" --page 2            # Next page
bili feed                               # Dynamic timeline
bili feed --offset 1234567890           # Next page via returned cursor
bili my-dynamics                         # My posted dynamics
bili dynamic-post "抽个奖，明天开奖"       # Publish text dynamic
bili dynamic-delete 123456789012345678   # Delete one dynamic

# Collections
bili favorites                          # Favorite folders
bili favorites <ID> --page 2            # Videos in a folder
bili following                          # Following list
bili watch-later                        # Watch later
bili history                            # Watch history

# Audio extraction
bili audio BV1ABcsztEcY                 # Download + split into 25s WAV segments
bili audio BV1ABcsztEcY --segment 60    # 60s per segment
bili audio BV1ABcsztEcY --no-split      # Full m4a, no splitting
bili audio BV1ABcsztEcY -o ~/data/      # Custom output directory

# Interactions
bili like BV1ABcsztEcY                  # Like
bili coin BV1ABcsztEcY                  # Give coin
bili triple BV1ABcsztEcY                # 一键三连 🎉
bili unfollow 946974                    # Unfollow by UID
bili like BV1ABcsztEcY --json           # Structured write result
bili coin BV1ABcsztEcY --yaml           # Structured write result
```

## Authentication

bilibili-cli uses a 3-tier authentication strategy:

1. **Saved credential** — loads from `~/.bilibili-cli/credential.json`
2. **Browser cookies** — auto-extracts from Chrome, Firefox, Edge, or Brave
3. **QR code login** — `bili login` displays a QR code in the terminal

Credentials are validated on use for authenticated commands. Expired cookies are automatically cleared, while transient network validation failures keep local credentials for best-effort fallback.
`bili status` exits with code `0` only when authenticated; otherwise it exits with `1`.

Most commands work without login. Subtitles, favorites/following/watch-later/history, feed, my-dynamics, and interactions require authentication. Write actions (like/coin/triple/unfollow/dynamic-post/dynamic-delete) require write-capable credential (`bili_jct`).

Audio extraction requires the optional `audio` dependency group (`av`).

## Structured Output

All `--json` / `--yaml` output uses the shared envelope from [SCHEMA.md](./SCHEMA.md).
Major commands now emit normalized payloads instead of raw upstream SDK blobs:

- `bili video` → `data.video`, `data.subtitle`, `data.ai_summary`, `data.comments`, `data.related`, `data.warnings`
- `bili hot` / `bili rank` → `data.items`
- `bili search` → normalized user/video lists
- `bili like` / `bili coin` / `bili triple` / `bili unfollow` → normalized write-action results

Structured errors now use more specific codes such as `not_authenticated`, `permission_denied`, `invalid_input`, `network_error`, `upstream_error`, and `not_found`.

## Use as AI Agent Skill

bilibili-cli ships with a [`SKILL.md`](./SKILL.md) that teaches AI agents how to use it.

### Agent Output Recommendation

If an AI agent needs machine-readable output, prefer `--yaml` first:

- `--yaml` is usually more token-efficient than pretty-printed JSON
- It is still easy to parse for agents and scripts
- Keep `--json` for `jq`, strict JSON-only tooling, or exact downstream schemas
- Non-TTY stdout defaults to YAML automatically
- Use `OUTPUT=yaml|json|rich|auto` to override the default mode

Examples:

```bash
bili status --yaml
bili video BV1ABcsztEcY --yaml
bili hot --max 5 --yaml
bili user-videos 946974 --max 3 --yaml
```

For agent usage, also prefer narrower queries (`--max`, `--page`, `--offset`) to avoid wasting context on oversized payloads.

When an AI agent is asked to summarize a video, it should fetch subtitles first. Subtitles usually contain the core content of the video and are the best primary source for summarization. Only fall back to AI summary, comments, or audio extraction when subtitles are unavailable or insufficient.

### [Skills CLI](https://github.com/vercel-labs/skills) (Recommended)

```bash
npx skills add jackwener/bilibili-cli
```

| Flag | Description |
| --- | --- |
| `-g` | Install globally (user-level, shared across projects) |
| `-a claude-code` | Target a specific agent |
| `-y` | Non-interactive mode |

### Manual Install

```bash
mkdir -p .agents/skills
git clone git@github.com:jackwener/bilibili-cli.git .agents/skills/bilibili-cli
```

Once added, AI agents that support the `.agents/skills/` convention will automatically discover and use bilibili-cli commands.

### ~~OpenClaw / ClawHub~~ (Deprecated)

> ⚠️ ClawHub install method is deprecated and no longer supported. Use [Skills CLI](#skills-cli-recommended) or Manual Install above.

## Troubleshooting

- `需要登录` / `not_authenticated` — Run `bili login` to scan QR code, or ensure you're logged in to bilibili.com in Chrome/Firefox/Edge/Brave.
- `HTTP 412` / `RateLimitError` — Bilibili anti-scraping triggered. Wait a moment and retry, or reduce `--max`.
- `无法提取 BV 号` / `InvalidBvidError` — Check the BV ID or URL format. Must be `BV` followed by 10 alphanumeric characters.
- `NetworkError` — Check your network connection. If behind a proxy, ensure it supports the target domain.
- `当前登录凭证不支持写操作` — Your saved cookies lack `bili_jct`. Run `bili login` to re-authorize with full write permission.

Structured error codes: `not_authenticated`, `permission_denied`, `invalid_input`, `network_error`, `upstream_error`, `not_found`, `rate_limited`, `internal_error`.

---

## 推荐项目

- [xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) — 小红书笔记与账号工作流 CLI
- [twitter-cli](https://github.com/jackwener/twitter-cli) — Twitter/X CLI 工具
- [discord-cli](https://github.com/jackwener/discord-cli) — Discord 本地优先同步、检索与导出 CLI
- [tg-cli](https://github.com/jackwener/tg-cli) — Telegram 本地优先同步、检索与导出 CLI

## 功能特性

- 🎬 **视频** — 详情、字幕、AI 总结、评论、相关推荐
- 🎵 **音频** — 提取视频音频，切分为语音识别 (ASR) 可用的 WAV 片段
- 👤 **用户** — UP 主资料、视频列表、关注列表
- 🔍 **搜索** — 按关键词搜索用户或视频
- 🔥 **发现** — 热门视频、全站排行榜
- 📰 **动态** — 关注的人的动态时间线
- 📂 **收藏** — 收藏夹浏览、稍后再看、观看历史
- 👍 **互动** — 点赞、投币、一键三连
- 🔐 **智能认证** — 自动提取浏览器 Cookie，或扫码登录
- 📊 **结构化输出** — 主要查询命令支持 `--yaml` 和 `--json`
- 🤖 **更适合 Agent** — stdout 不是 TTY 时默认输出 YAML，也可以用 `OUTPUT=yaml|json|rich|auto` 覆盖
- 🧱 **规范化 payload** — 结构化输出在命令层做了收口，不再直接暴露原始上游 SDK 返回

## 安装

```bash
# 推荐：uv tool（快速、隔离环境）
uv tool install bilibili-cli

# 或者：pipx
pipx install bilibili-cli

# 如果需要音频提取功能
uv tool install "bilibili-cli[audio]"
# 或
pipx install "bilibili-cli[audio]"
```

升级到最新版本：

```bash
uv tool upgrade bilibili-cli
# 或：pipx upgrade bilibili-cli
```

> **提示：** 建议定期升级，避免因版本过旧导致的 API 调用异常。

或从源码安装：

```bash
git clone git@github.com:jackwener/bilibili-cli.git
cd bilibili-cli
uv sync
```

开发环境验证：

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
uv run python -m mypy bili_cli
```

如果项目目录发生过移动，导致旧的 virtualenv wrapper 失效，可重新执行：

```bash
uv sync --extra dev --reinstall
```

## 使用示例

```bash
# 登录与账号
bili status                    # 检查登录状态
bili status --yaml             # 结构化认证状态
bili login                     # 扫码登录
bili whoami                    # 查看个人信息（等级、硬币、粉丝数）
bili whoami --yaml             # 结构化个人信息

# 视频
bili video BV1ABcsztEcY                 # 视频详情
bili video BV1ABcsztEcY --subtitle      # 显示字幕（纯文本）
bili video BV1ABcsztEcY --subtitle-timeline        # 显示带时间线的字幕
bili video BV1ABcsztEcY -st --subtitle-format srt  # 导出为 SRT
bili video BV1ABcsztEcY --ai            # AI 总结
bili video BV1ABcsztEcY --comments      # 热门评论
bili video BV1ABcsztEcY --related       # 相关推荐
bili video BV1ABcsztEcY --yaml          # 适合 AI Agent 的 YAML
bili video BV1ABcsztEcY --json          # 规范化 JSON envelope
bili video BV1ABcsztEcY --subtitle-timeline --comments --json  # 额外内容也会进入 payload

# 用户
bili user 946974                        # UP 主资料
bili user "影视飓风"                     # 按用户名搜索
bili user-videos 946974 --max 20        # 视频列表

# 发现
bili hot                                # 热门视频（第1页）
bili hot --page 2 --max 10              # 第2页，前10条
bili rank                               # 全站排行榜（3日）
bili rank --day 7 --max 30              # 7日榜，前30条
bili search "关键词"                     # 搜索用户
bili search "关键词" --type video --max 5 # 搜索视频（前5条）
bili search "关键词" --page 2            # 第2页结果
bili feed                               # 动态时间线
bili feed --offset 1234567890           # 使用上一页游标翻页
bili my-dynamics                         # 我发布的动态
bili dynamic-post "抽个奖，明天开奖"       # 发布文字动态
bili dynamic-delete 123456789012345678   # 删除单条动态

# 收藏
bili favorites                          # 收藏夹列表
bili following                          # 关注列表
bili watch-later                        # 稍后再看
bili history                            # 观看历史

# 音频提取
bili audio BV1ABcsztEcY                 # 下载并切分为 25 秒 WAV 片段
bili audio BV1ABcsztEcY --segment 60    # 每段 60 秒
bili audio BV1ABcsztEcY --no-split      # 完整 m4a，不切分
bili audio BV1ABcsztEcY -o ~/data/      # 自定义输出目录

# 互动
bili like BV1ABcsztEcY                  # 点赞
bili coin BV1ABcsztEcY                  # 投币
bili triple BV1ABcsztEcY                # 一键三连 🎉
bili unfollow 946974                    # 取消关注（按 UID）
bili like BV1ABcsztEcY --json           # 结构化写操作结果
bili coin BV1ABcsztEcY --yaml           # 结构化写操作结果
```

## 认证策略

bilibili-cli 采用三级认证策略：

1. **已保存凭证** — 从 `~/.bilibili-cli/credential.json` 加载
2. **浏览器 Cookie** — 自动从 Chrome、Firefox、Edge、Brave 提取
3. **扫码登录** — `bili login` 在终端显示二维码

需要认证的命令会自动校验凭证。过期 Cookie 会自动清除；如果只是临时网络异常，不会误清本地凭证（会以 best-effort 继续尝试）。

大部分命令无需登录。字幕、收藏夹、动态和互动操作需要登录。写操作（like/coin/triple/unfollow/dynamic-post/dynamic-delete）需要可写凭证（包含 `bili_jct`）。

## 结构化输出

所有 `--json` / `--yaml` 输出都使用 [SCHEMA.md](./SCHEMA.md) 里的 envelope。
主要命令现在会返回命令层规范化后的 payload，例如：

- `bili video` → `data.video`、`data.subtitle`、`data.ai_summary`、`data.comments`、`data.related`、`data.warnings`
- `bili hot` / `bili rank` → `data.items`
- `bili search` → 规范化后的用户或视频列表
- `bili like` / `bili coin` / `bili triple` / `bili unfollow` → 标准化写操作结果

结构化错误码也区分成了 `not_authenticated`、`permission_denied`、`invalid_input`、`network_error`、`upstream_error`、`not_found` 等类型，便于脚本或 agent 做恢复和分支处理。

## AI Agent 使用建议

如果 AI Agent 需要机器可读输出，默认优先 `--yaml`：

- `--yaml` 通常比格式化 JSON 更省 token
- 对 agent 来说仍然容易解析
- 只有在要配合 `jq` 或下游必须是 JSON 时，再使用 `--json`
- stdout 不是 TTY 时会默认自动输出 YAML
- 也可以用 `OUTPUT=yaml|json|rich|auto` 强制覆盖默认输出模式

示例：

```bash
bili status --yaml
bili video BV1ABcsztEcY --yaml
bili hot --max 5 --yaml
bili user-videos 946974 --max 3 --yaml
```

另外，agent 应尽量配合 `--max`、`--page`、`--offset` 缩小结果集，避免把不必要的数据带进上下文。

如果 agent 要帮用户总结视频，应该优先拉字幕。字幕通常就是视频核心内容的第一手来源，最适合做 summary；只有在没有字幕或字幕明显不足时，再退回到 AI summary、评论或音频提取。

音频提取功能需要安装可选依赖组 `audio`（即 `av`）。

## 作为 AI Agent Skill 使用

bilibili-cli 自带 [`SKILL.md`](./SKILL.md)，让 AI Agent 能自动学习并使用本工具。

### [Skills CLI](https://github.com/vercel-labs/skills)（推荐）

```bash
npx skills add jackwener/bilibili-cli
```

| 参数 | 说明 |
| --- | --- |
| `-g` | 全局安装（用户级别，跨项目共享） |
| `-a claude-code` | 指定目标 Agent |
| `-y` | 非交互模式 |

### 手动安装

```bash
mkdir -p .agents/skills
git clone git@github.com:jackwener/bilibili-cli.git .agents/skills/bilibili-cli
```

添加后，支持 `.agents/skills/` 的 AI Agent 会自动发现并使用 bilibili-cli 命令。

### ~~OpenClaw / ClawHub~~（已过时）

> ⚠️ ClawHub 安装方式已过时，不再支持。请使用上方的 Skills CLI 或手动安装。

## 常见问题

- `需要登录` — 执行 `bili login` 扫码登录，或确保已在 Chrome/Firefox/Edge/Brave 登录 bilibili.com
- `HTTP 412` / `RateLimitError` — B 站反爬触发，稍等后重试，或减小 `--max`
- `无法提取 BV 号` — 检查 BV 号或 URL 格式，必须是 `BV` + 10 位字母数字
- `NetworkError` — 检查网络连接
- `当前登录凭证不支持写操作` — 保存的 Cookie 缺少 `bili_jct`，执行 `bili login` 重新授权

## License

Apache-2.0
