# Changelog

## Unreleased

- Fix `bili login` saving empty credentials when Bilibili web QR poll returns a ticket URL without `SESSDATA`/`bili_jct`; switch QR login to the TV channel and reject empty sessions
- Best-effort fill `buvid3`/`buvid4` after QR login to reduce HTTP 412 wind-control failures

## 0.5.0

- Add subtitle timeline output via `bili video --subtitle-timeline` / `-st`
- Add `--subtitle-format timeline|srt`
- Keep subtitle timeline compatible with current `--yaml` / `--json` command surface
- Ensure subtitle timeline requests load optional credentials like plain subtitles
- Restore README badges and fix CI type-checking with `types-PyYAML`
