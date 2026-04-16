---
name: bilibili-cli
description: CLI skill for Bilibili (哔哩哔哩, B站) with token-efficient YAML output for AI agents to browse videos, users, search, trending, dynamics, favorites, and interactions from the terminal
author: jackwener
version: "0.6.2"
tags:
  - bilibili
  - 哔哩哔哩
  - b站
  - video
  - social-media
  - cli
---

# bilibili-cli Skill

A CLI tool for interacting with Bilibili (哔哩哔哩). Use it to fetch video info, search content, browse user profiles, and perform interactions like liking or triple-clicking.

## Agent Defaults

When you need machine-readable output:

1. Prefer `--yaml` first because it is usually more token-efficient than pretty JSON.
2. Use `--json` only when downstream tooling strictly requires JSON.
3. Keep result sets small with `--max`, `--page`, or `--offset`.
4. Prefer specific commands over broad ones. Example: use `bili user-videos 946974 --max 3 --yaml` instead of fetching large timelines.
5. When summarizing a video, fetch subtitles first. Subtitles usually contain the video's core content and are the best primary source for summaries.
6. Only fall back to `--ai`, comments, or audio extraction when subtitles are unavailable or clearly insufficient.

## Prerequisites

```bash
# Install (requires Python 3.10+)
uv tool install bilibili-cli
# Or: pipx install bilibili-cli

# If you need audio extraction support (requires PyAV)
uv tool install "bilibili-cli[audio]"
# Or: pipx install "bilibili-cli[audio]"

# Upgrade to latest (recommended to avoid API errors)
uv tool upgrade bilibili-cli
# Or: pipx upgrade bilibili-cli
```

## Authentication

Most read commands work without login. Subtitles, favorites/following/watch-later/history, feed, and interactions require login.

```bash
bili status                    # Check if logged in (exit 0 = yes, 1 = no)
bili login                     # QR code login (if not authenticated)
```

Authentication auto-detects local browser cookies (Chrome/Firefox/Edge/Brave). If cookies are found and valid, no manual login needed. Credentials are saved to `~/.bilibili-cli/credential.json`.

## Command Reference

### Video

```bash
# Get video details (accepts BV ID or full URL)
bili video BV1ABcsztEcY
bili video https://www.bilibili.com/video/BV1ABcsztEcY

# Options
bili video BV1ABcsztEcY --subtitle            # Show subtitles (plain text)
bili video BV1ABcsztEcY --subtitle-timeline   # Show subtitles with timestamps
bili video BV1ABcsztEcY -st --subtitle-format srt  # Export as SRT format
bili video BV1ABcsztEcY --ai            # Show B站 AI summary
bili video BV1ABcsztEcY --comments      # Show top comments
bili video BV1ABcsztEcY --related       # Show related videos
bili video BV1ABcsztEcY --yaml          # Token-efficient YAML output
bili video BV1ABcsztEcY --json          # Structured JSON envelope
```

### User

```bash
# Look up user profile (by UID or username)
bili user 946974
bili user "影视飓风"

# List user's videos
bili user-videos 946974 --max 20
bili user-videos "影视飓风" --yaml
```

### Search

```bash
# Search users (default)
bili search "关键词"

# Search videos
bili search "关键词" --type video

# Pagination and limit
bili search "关键词" --type video --max 5
bili search "关键词" --page 2
```

### Discovery

```bash
bili hot                       # Trending/popular videos
bili hot --page 2 --max 10     # Page 2, limit 10
bili rank                      # Site-wide ranking (3-day)
bili rank --day 7 --max 30     # 7-day ranking, top 30
bili feed                      # Dynamic timeline (requires login)
bili feed --offset 1234567890  # Next page via returned cursor
bili my-dynamics               # My posted dynamics (requires login)
bili dynamic-post "hello"      # Publish text dynamic (requires write credential)
bili dynamic-delete 123456789  # Delete one dynamic (requires write credential)
```

### Collections (require login)

```bash
bili favorites                 # List favorite folders
bili favorites <ID> --page 2   # Videos in a folder
bili following                 # Following list
bili watch-later               # Watch later list
bili history                   # Watch history
```

### Audio Extraction

Requires `bilibili-cli[audio]` extra (PyAV). Install with `uv tool install "bilibili-cli[audio]"`.

```bash
# Download audio and split into ASR-ready WAV segments (25s each, 16kHz mono)
bili audio BV1ABcsztEcY                 # Split to /tmp/bilibili-cli/{title}/
bili audio BV1ABcsztEcY --segment 60    # 60s per segment
bili audio BV1ABcsztEcY --no-split      # Full m4a file, no splitting
bili audio BV1ABcsztEcY -o ~/data/      # Custom output directory
```

### Interactions (require login)

```bash
bili like BV1ABcsztEcY         # Like a video
bili like BV1ABcsztEcY --undo  # Unlike
bili coin BV1ABcsztEcY         # Give 1 coin
bili coin BV1ABcsztEcY -n 2    # Give 2 coins
bili triple BV1ABcsztEcY       # 一键三连 (like + coin + favorite)
bili unfollow 946974           # Unfollow by UID
```

### Account

```bash
bili status                    # Quick login check
bili status --yaml             # Structured auth status
bili whoami                    # Detailed profile info
bili whoami --yaml              # Profile as YAML
bili whoami --json              # Profile as JSON
bili login                     # QR code login
bili logout                    # Clear credentials
```

## Structured Output

Major query commands support both `--yaml` and `--json` for machine-readable output. Prefer YAML for agent use:

```bash
bili status --yaml                                # Quick structured auth check
bili video BV1ABcsztEcY --yaml                       # Preferred for AI agents
bili hot --max 5 --yaml                             # Smaller, token-efficient payload
bili user 946974 --json | jq -r '.data.user.name'   # JSON when jq is needed
```

When stdout is not a TTY, `bilibili-cli` defaults to YAML automatically.
Use `OUTPUT=yaml|json|rich|auto` to override the default output mode.
All machine-readable output uses the envelope documented in [SCHEMA.md](./SCHEMA.md).

## Debugging

```bash
bili -v <command>              # Enable verbose/debug logging for any command
```

## Common Patterns for AI Agents

```bash
# For video summarization, fetch subtitles first
bili video BV1ABcsztEcY --subtitle

# Only use AI summary as a fallback or secondary signal
bili video BV1ABcsztEcY --ai

# Get comments for sentiment analysis
bili video BV1ABcsztEcY --comments

# Extract audio for speech-to-text (ASR)
# Segments are saved to /tmp/bilibili-cli/{title}/seg_000.wav, seg_001.wav, ...
bili audio BV1ABcsztEcY --segment 25

# Find a user's latest video BV ID with minimal payload
bili user-videos 946974 --max 1 --yaml

# Check if logged in before performing actions
bili status && bili like BV1ABcsztEcY

# Search and inspect the first few results
bili search "topic" --type video --max 3 --yaml
```

### Workflow: Video Content Analysis

```bash
# 1. Search for a topic
bili search "AI" --type video --max 5

# 2. Get subtitles first for summarization
bili video BV1xxx --subtitle

# 3. If subtitles are missing or incomplete, try AI summary
bili video BV1xxx --ai

# 4. If there is still not enough content, extract audio for ASR
bili audio BV1xxx --segment 25

# 5. Get comments for audience reaction
bili video BV1xxx --comments
```

### Workflow: UP主 Research

```bash
# 1. Look up UP主 profile
bili user "影视飓风"

# 2. Get their recent videos
bili user-videos 946974 --max 10

# 3. Inspect a specific video
bili video BV1xxx --ai --comments
```

## Error Handling

- Commands exit with code 0 on success, non-zero on failure
- Error messages are prefixed with ❌
- Login-required commands show ⚠️ with instruction to run `bili login`
- Invalid BV IDs show a clear error message

## Safety Notes

- Do not ask users to share raw credential/cookie values in chat logs.
- Prefer local browser cookie extraction over manual secret copy/paste.
- If auth fails, ask the user to re-login via `bili login`.
