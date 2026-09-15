# Compact Wizard Screen Design

Date: 2026-09-15
Status: Approved by product owner

## Problem

The first-run wizard screen of the CLI TUI (`cli/src/nasmanager/ui/wizard.py`)
looks visually heavy: Textual renders inputs with thick borders and large
paddings, labels have their own padding, the button stretches wide. The
owner wants a simpler, more compact look while keeping the same fields.

## Accepted approach: Compact stack (Option A)

Keep the current structure — label + input per field, stacked — but tame the
visuals with a small CSS block on `WizardScreen`.

### Structure (unchanged)

- Title `Настройка NAS Manager` (#title)
- 4 pairs: `Адрес сервера:` (#server_url), `Логин:` (#username),
  `Пароль:` (#password), `Корневая папка для шар:` (#mount_root)
- Button `Далее` (#next)
- Error line (#error)

Behavior is unchanged: validation ("Все поля обязательны"), login via
`ApiClient.login`, error display, `Config.save()`, `pop_screen()`.

### CSS (new on WizardScreen)

- `#wizard` container: limited width (~68 cols), centered, tight padding.
- Labels: no own padding, muted color (`$text-muted`).
- Inputs: single-line (height 1), no thick border (`border: none`),
  subtle `$surface` fill, small padding, small margin below each field.
- `#next` button: narrow fixed width (~16 cols).
- Title: compact bold, small bottom margin.
- `#error`: `$error` color.

### Verification

- `just cli-test` — 18 passed, 1 skipped (unchanged).
- Headless pty smoke run of the wizard — renders with single-line inputs,
  visibly more compact than before.