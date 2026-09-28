# Installation Guide

> **Affected versions: `bilibili-cli <= 0.6.2` (everything on PyPI).**
> `bili login` reports success but saves an empty credential, so every logged-in
> command fails with `not_authenticated`. See [Symptom](#symptom) and
> [Install the fixed version](#install-the-fixed-version).
>
> 中文版见下方 [中文说明](#中文说明)。

---

## Symptom

Bilibili changed its **web** QR login response in 2026-08. The success payload
no longer carries credentials in `data.url`'s query string; it now returns a
`passport.biligame.com/x/passport-login/web/crossDomain?ticket=...` link, and
the real `SESSDATA` / `bili_jct` / `DedeUserID` are delivered through
`Set-Cookie` response headers when that link is followed.

`bilibili-api-python` (latest release `17.4.2`; this repo's `uv.lock` pins
`17.4.1`; its repository is **archived** and will never ship another release)
only parses the URL query string. So it reports `DONE` and then writes empty
strings:

```console
$ bili login
✅ 登录成功！凭证已保存          # claims success

$ bili status
not_authenticated                # exit code 1
```

Confirm it by inspecting the credential file — `ac_time_value` is populated
(it comes from a different code path) while `sessdata` / `bili_jct` are empty:

```bash
grep -E '"(sessdata|bili_jct|ac_time_value)"' ~/.bilibili-cli/credential.json
#   "sessdata": "",          <-- empty: the bug
#   "bili_jct": "",          <-- empty: the bug
#   "ac_time_value": "..."   <-- populated, which is why login "succeeded"
```

Consequence: `bili favorite`, `bili watch-later`, `bili history`, `bili feed`,
`bili like`, `bili coin` and every other authenticated command are unusable,
and **write** operations additionally report
`当前登录凭证不支持写操作` because `bili_jct` is empty.

## Why it is not fixed upstream

| | Status |
|---|---|
| `public-clis/bilibili-cli` `main` | Last commit `dbe2855`, 2026-03-14. No login fix. |
| PyPI `bilibili-cli` | Still `0.6.2` — the broken version. |
| `Nemo2011/bilibili-api` | `archived`, last release `17.4.2` (`uv.lock` pins `17.4.1`). Unfixable upstream. |
| PR [#27](https://github.com/public-clis/bilibili-cli/pull/27) | **OPEN**, mergeable, but unreviewed since 2026-08-17. |

The fix therefore has to be installed from a git ref, not from PyPI. Once PR #27
(or an equivalent) is merged and a new version is published, this document is
obsolete and plain `uv tool install bilibili-cli` works again.

## Install the fixed version

The fix is commit **`6962d5b`** ("fix(login): support Bilibili crossDomain
QR-login response format"). Requires Python 3.10+.

Pick **one** of the three paths below.

### Path 1 — Install the CLI (recommended)

Pinned to the exact fix commit, so the installed version is reproducible:

```bash
uv tool install "bilibili-cli @ git+https://github.com/ZeroMarker/bilibili-cli.git@6962d5b"

# or, with pipx
pipx install "bilibili-cli @ git+https://github.com/ZeroMarker/bilibili-cli.git@6962d5b"
```

If you need audio extraction (adds PyAV), use PEP 508 direct-reference syntax
with the extra:

```bash
uv tool install "bilibili-cli[audio] @ git+https://github.com/ZeroMarker/bilibili-cli.git@6962d5b"
```

To track the branch instead of pinning a commit, drop the `@<sha>` suffix.
To upgrade a previously installed copy:

```bash
uv tool upgrade --reinstall bilibili-cli     # or: pipx upgrade bilibili-cli
```

### Path 2 — Install as an AI agent skill

```bash
npx skills add ZeroMarker/bilibili-cli
```

| Flag | Description |
| --- | --- |
| `-g` | Install globally (user-level, shared across projects) |
| `-a claude-code` | Target a specific agent |
| `-y` | Non-interactive mode |

> Use the repository you actually want. The upstream README's
> `npx skills add jackwener/bilibili-cli` installs a copy that does **not**
> contain the login fix.

### Path 3 — Manual install into a skill directory

```bash
mkdir -p .agents/skills
git clone https://github.com/ZeroMarker/bilibili-cli.git .agents/skills/bilibili-cli
cd .agents/skills/bilibili-cli && git checkout 6962d5b
```

AI agents that support the `.agents/skills/` convention will discover it
automatically. Run the CLI from that checkout with `uv run bili ...`, or
install it globally using Path 1.

### Replace an existing installation

Both PyPI and git installs use the same distribution name, so remove the old
copy first or the installer will report a conflict:

```bash
uv tool uninstall bilibili-cli     # or: pipx uninstall bilibili-cli
```

## Clear the broken credential

A credential file written by `0.6.2` contains empty strings and will keep
failing even after upgrading. Delete it and log in again:

```bash
bili logout        # removes ~/.bilibili-cli/credential.json
bili login         # scan the QR code, then confirm on your phone
```

## Verify the fix

```bash
bili status
# expect: authenticated: true   (exit code 0)

grep -E '"(sessdata|bili_jct)"' ~/.bilibili-cli/credential.json
# expect: both non-empty
```

A single self-contained check:

```bash
bili status >/dev/null 2>&1 && echo "OK: credential is valid" || echo "FAIL: still unauthenticated"
```

If `bili login` succeeds but `bili status` still fails, confirm you are actually
running the patched build:

```bash
python -c "from bili_cli.auth import _patched_check_state; print('patched:', _patched_check_state.__name__)"
# expect: patched: _patched_check_state
# on 0.6.2: ImportError: cannot import name '_patched_check_state' from 'bili_cli.auth'
```

**Do not use `bili --version` to check this.** It reads the installed
distribution metadata, which is still `0.6.2` for the patched build because the
version was never bumped — it prints the same string either way:

```console
$ bili --version
bili, version 0.6.2      # identical on the broken and the fixed build
```

If the status check still fails, re-run `bili login` from a clean credential
file, and check for a real login-error message instead of a false success.

## Roll back

```bash
uv tool uninstall bilibili-cli
uv tool install bilibili-cli        # installs 0.6.2 from PyPI again
```

Note that rolling back reintroduces the empty-credential bug for Bilibili's
current login flow.

## Related

- Upstream PR: https://github.com/public-clis/bilibili-cli/pull/27
- Upstream issue tracker: https://github.com/public-clis/bilibili-cli/issues
- Related unmerged PR covering the same bug: https://github.com/public-clis/bilibili-cli/pull/29

---

# 中文说明

> **受影响版本：PyPI 上的 `bilibili-cli <= 0.6.2`（即目前所有已发布版本）。**
> 表现为 `bili login` 提示成功，但保存的凭证是空的，随后所有需要登录的命令都报
> `not_authenticated`。详见[症状](#症状)与[安装已修复的版本](#安装已修复的版本)。

## 症状

Bilibili 在 2026-08 改版了 **WEB 端**扫码登录的成功响应：`data.url` 不再把凭证放在
query string 里，而是返回一个
`passport.biligame.com/x/passport-login/web/crossDomain?ticket=...` 跨域票据链接，
真正的 `SESSDATA` / `bili_jct` / `DedeUserID` 改为**跟随该链接时通过 `Set-Cookie`
响应头下发**。

而 `bilibili-api-python`（最新发布为 `17.4.2`；本仓库 `uv.lock` 固定在 `17.4.1`；
其仓库已 **archived**，不会再发版）只解析 URL 的 query string，
于是它会先判定 `DONE`，再把空字符串写进凭证文件：

```console
$ bili login
✅ 登录成功！凭证已保存          # 提示成功

$ bili status
not_authenticated                # 退出码 1
```

检查凭证文件即可确认——`ac_time_value` 有值（它来自另一条 `refresh_token` 路径），
但 `sessdata` / `bili_jct` 是空的：

```bash
grep -E '"(sessdata|bili_jct|ac_time_value)"' ~/.bilibili-cli/credential.json
#   "sessdata": "",          <-- 空：即此 bug
#   "bili_jct": "",          <-- 空：即此 bug
#   "ac_time_value": "..."   <-- 有值，所以登录「成功」了
```

后果：`bili favorite`、`bili watch-later`、`bili history`、`bili feed`、
`bili like`、`bili coin` 等所有需登录的命令全部不可用；**写操作**还会额外报
`当前登录凭证不支持写操作`，因为 `bili_jct` 为空。

## 为什么上游还没修

| | 状态 |
|---|---|
| `public-clis/bilibili-cli` `main` | 最后提交 `dbe2855`（2026-03-14），无登录修复 |
| PyPI `bilibili-cli` | 仍是 `0.6.2`，即坏版本 |
| `Nemo2011/bilibili-api` | `archived`，最后版本 `17.4.2`（`uv.lock` 固定 `17.4.1`），上游不可能再修 |
| PR [#27](https://github.com/public-clis/bilibili-cli/pull/27) | **OPEN**，可干净合并，但自 2026-08-17 起无人 review |

所以修复只能**从 git ref 安装**，不能从 PyPI 装。等 PR #27（或等价方案）合并并发布新版本后，
本文档即失效，回到普通的 `uv tool install bilibili-cli` 即可。

## 安装已修复的版本

修复提交为 **`6962d5b`**（`fix(login): support Bilibili crossDomain QR-login
response format`）。需要 Python 3.10+。以下三条路径**任选其一**。

### 方式一：安装 CLI（推荐）

锁定到具体提交，装出来的版本可复现：

```bash
uv tool install "bilibili-cli @ git+https://github.com/ZeroMarker/bilibili-cli.git@6962d5b"

# 或用 pipx
pipx install "bilibili-cli @ git+https://github.com/ZeroMarker/bilibili-cli.git@6962d5b"
```

如果需要音频提取（会引入 PyAV），用 PEP 508 direct-reference 语法加 extra：

```bash
uv tool install "bilibili-cli[audio] @ git+https://github.com/ZeroMarker/bilibili-cli.git@6962d5b"
```

若想跟踪分支而非锁定提交，去掉 `@<sha>` 后缀即可。升级已安装的版本：

```bash
uv tool upgrade --reinstall bilibili-cli     # 或：pipx upgrade bilibili-cli
```

### 方式二：作为 AI agent skill 安装

```bash
npx skills add ZeroMarker/bilibili-cli
```

| 参数 | 说明 |
| --- | --- |
| `-g` | 全局安装（用户级，跨项目共享） |
| `-a claude-code` | 指定 agent |
| `-y` | 非交互模式 |

> 务必确认仓库名是你真正要的那一个。上游 README 里的
> `npx skills add jackwener/bilibili-cli` 装到的是**不含此登录修复**的副本。

### 方式三：手动装进 skill 目录

```bash
mkdir -p .agents/skills
git clone https://github.com/ZeroMarker/bilibili-cli.git .agents/skills/bilibili-cli
cd .agents/skills/bilibili-cli && git checkout 6962d5b
```

支持 `.agents/skills/` 约定的 AI agent 会自动发现它。在该目录内用
`uv run bili ...` 运行 CLI，或按方式一全局安装。

### 替换已有安装

PyPI 版和 git 版使用同一个分发名，需要先卸载旧版本，否则安装器会报冲突：

```bash
uv tool uninstall bilibili-cli     # 或：pipx uninstall bilibili-cli
```

## 清除损坏的凭证

`0.6.2` 写出的凭证文件里是空字符串，升级后依然会失败。删掉并重新登录：

```bash
bili logout        # 删除 ~/.bilibili-cli/credential.json
bili login         # 扫码后在手机上确认
```

## 验证修复生效

```bash
bili status
# 期望：authenticated: true   （退出码 0）

grep -E '"(sessdata|bili_jct)"' ~/.bilibili-cli/credential.json
# 期望：两者都非空
```

一条命令自检：

```bash
bili status >/dev/null 2>&1 && echo "OK: credential is valid" || echo "FAIL: still unauthenticated"
```

如果 `bili login` 成功但 `bili status` 仍失败，确认跑的是打过补丁的构建：

```bash
python -c "from bili_cli.auth import _patched_check_state; print('patched:', _patched_check_state.__name__)"
# 期望：patched: _patched_check_state
# 在 0.6.2 上：ImportError: cannot import name '_patched_check_state'
```

**不要用 `bili --version` 判断。** 它读的是已安装的分发元数据，而修复版从未 bump 版本号，
所以两边打印的是同一个字符串：

```console
$ bili --version
bili, version 0.6.2      # 坏版本和修复版完全一样
```

若状态检查仍失败，请在凭证文件已清空的前提下重新执行 `bili login`，并留意
`bili login --help` 中是否有明确的登录错误提示，而不是虚假的成功提示。

## 回滚

```bash
uv tool uninstall bilibili-cli
uv tool install bilibili-cli        # 重新装回 PyPI 的 0.6.2
```

注意回滚会让空凭证 bug 重新出现（B 站当前登录流程下必然复现）。

## 相关链接

- 上游 PR：https://github.com/public-clis/bilibili-cli/pull/27
- 上游 issue：https://github.com/public-clis/bilibili-cli/issues
- 同一 bug 的另一个未合并 PR：https://github.com/public-clis/bilibili-cli/pull/29
