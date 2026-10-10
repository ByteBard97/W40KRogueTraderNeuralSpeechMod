# Porting pages onto the redesign foundation

Phase 1 is in `tools/studio/web`. Read `shared.css` and `screens/00-design-system.png` for the look; this file lists what exists in code.
Live gallery: `/styleguide` (dev server, or a build made with `VITE_STYLEGUIDE=1 npx vite build`). Not in normal builds.

## Tokens and base
- `src/styles/tokens.css`: every token from `shared.css` (`--n-0..9`, roles, `--accent*`, `--good/bad/warn/info` + `-tint`, `--*-line` outlines, spacing `--s-1..7`, radius, `--e-1..3`, `--hit*`, `--bar-h`, `--topbar-h`, `--z-*`). Dark only. Legacy aliases (`--card --fg --dim --ok --acc --on-acc`) still exist for unported pages; do not use them in new code, delete them when the last page is ported.
- `src/styles/base.css`: reset, focus ring, legacy bare `button/input/select` styling (low specificity; component classes override it), and global helpers: `.page .page-head .page-title .page-sub .split > .main/.side .sticky .vs-card .divider .list-head .saved .tbl-wrap table.tbl .field (+ .lbl) .spinner .mono .num .muted .dim .vh .hide-sm`.
- Component look (button, chip, tag, flag, dot, row, play, seg, toast...) lives in each component's `<style scoped>`, NOT as global classes. Do not write `.btn`, `.chip`, `.row` by hand; use the component. (Global names would collide with the old pages' scoped classes.)
- Fonts: `public/fonts/*.woff2`, `src/styles/fonts.css` (urls `/fonts/...`). Display face only for `.page-title` and the brand.
- Page frame: `<div class="page"><div class="page-head"><h1 class="page-title">..</h1><span class="page-sub">..</span></div> ... </div>` (max 1480px, its own padding).

## Shell (done, mounted by `AppShell.vue`)
TopBar (brand, nav with counts from `stores/navCounts.ts`, ModelPill, `?` button), AudioBar, ToastStack, ShortcutOverlay, global audio keys. Pages add nothing for these.

## Composables and stores
- `composables/globalAudio.ts` `useGlobalAudio()`: the ONE `<audio>`. `state` (id, title, subtitle, isPlaying, current, duration, rate, loop, volume, transport), `playing` (id or null), `progress` (0..1), `play(id, url?, {title, subtitle})` (same id toggles pause/resume), `switchTo(id, url, meta, 'fraction'|'seconds')` (keeps playhead), `toggle stop seek seekBy setRate setLoop setVolume`, `setTransport({prev,next}) / clearTransport(t)` (fills the bar's previous/next buttons and the `,` `.` keys; set in onMounted, clear in onBeforeUnmount).
- `useAudioPlayer()`: old API (`play(id, url?, meta?)`, `playing`, `stop`) on top of the above; existing consumers unchanged. New code: use `InlinePlay` or `useGlobalAudio`.
- `useAudioKeys()`: mounted once by the shell. Space, Left/Right 1 s, Shift+Left/Right 5 s (as the design sheet says), `,` `.` prev/next, L loop, `[` `]` speed. Skips typing targets, events a page already `preventDefault`ed (so `useQaKeys` Space wins), and Space while a button/link has focus (InlinePlay/AudioBar blur themselves after a mouse click so Space works right after clicking play).
- `useShortcuts({title, groups:[{title, items:[{label, keys:[...]}]}]})`: call in a page's setup to feed the overlay (registered on mount, cleared on unmount). Global keys are appended automatically. `useShortcutOverlay()` gives `open/show/hide/toggle`.
- `useToasts()`: `ok(msg)`, `error(msg, retry?)`, `undo(msg, undoFn)` (Z runs the newest undo), `dismiss`, `clear`. Replaces modal confirms: do the action, then offer `undo`.
- `stores/model.ts`: adds `busyElapsed` (s) and `retry()`. `stores/navCounts.ts`: `load()` is called by TopBar; call `useNavCountsStore().load()` again after a page changes a count.
- `utils/keys.ts`: `isTypingTarget(target)`, `blurAfterPointer(e)`. `utils/time.ts`: `formatClock(s)` 0:07, `formatPlayhead(s)` 0:01.8.

## Components (`src/components/ui`, plus `shared/`)
| Component | Props / slots / events |
|---|---|
| `Btn` | `variant` default/primary/ghost/danger/good, `size` sm/md/lg, `icon` (square; give `label`), `kbd` hint, `label` (aria-label), `pressed` (aria-pressed), `type`. Attrs like `disabled`, `@click` pass through. |
| `Kbd` | slot keycap. |
| `Icon` | `name` check/x/warn/chev/play/pause/prev/next/search/loop/volume/up/star/brand, `size`. Decorative. |
| `Seg` | generic: `options [{value,label,disabled?}]`, `v-model`, `ariaLabel` (required), `accent`. |
| `FilterChips` | `options [{value,label,count?}]`, `v-model` (string, string[] with `multiple`, or null), `clearable`, `ariaLabel`. |
| `Tag` | `variant` plain/real/designed/slot/bank/nobank. |
| `Flag` | `tone` warn/bad/info, `icon`. |
| `ScoreChip` | `tone` neutral/ok/hot/none. |
| `StatusDot` | `status` idle/progress/picked/done/good/bad/flag, `label` (accessible name). Each state has its own shape/fill. |
| `FilterBar` | container; put `SearchField` (give it `class="grow"`), `SelectField`, `Seg` inside. |
| `SearchField` | `v-model`, `placeholder`, `label`, `focusKey` (default true: `/` focuses it; use one per page). |
| `SelectField` | `label`, `options [{value,label}]`, `v-model`. |
| `ActiveFilters` | `filters [{key,label}]`, `shown`, `total`; emits `remove(key)`, `clear`. Renders nothing when empty. |
| `shared/SectionCard` | `title`, `summary` (always visible, so it reads when closed), `step`, `collapsedByDefault`; slots default and `actions`. Old API kept. |
| `DataRow` | `selected`, `as` div/a/li, `href`; slots `lead`, default, `meta`, `end`. Wrap rows in `<div class="vs-card">`. |
| `Toast` | static toast: `kind` ok/err, `actionLabel`, `actionKey`, emits `action`. Real toasts come from `useToasts()` via the shell's `ToastStack`. |
| `InlineError` | `title`; slot is the detail. |
| `InlineConfirm` | `confirmLabel`, `cancelLabel`; the slot MUST state the consequence; Enter confirms, Esc cancels. |
| `SavedIndicator` | `ago`. |
| `BusyJobCard` | `title`, `elapsedS`, `progress` 0..1 (omit = indeterminate), `etaS`, `detail`, `cancelable`; emits `cancel`. |
| `Skeleton` | `rows`. |
| `shared/EmptyState` | `state` empty/loading/error, `title`, `message`, default slot for an action. Old `message`-only use works. |
| `InlinePlay` | `id` (repo path or key; null = unavailable), `src`, `title`, `subtitle`, `large`, `waveform` (decorative bars + progress + clock), `unavailableReason`. |
| `AudioBar` | shell-mounted; `static` only for the styleguide. |
| `SeekTrack` | `v-model` fraction, `label`; a range input over a drawn bar. |
| `ABCompareStrip` | `clips: ClipItem[]` (`{key,label,sub?,path,src?,title?}`; path null = disabled slot), `line` (text under review), `v-model` (selected key, optional), `hotkeys` (binds 1-4 on the document; enable on one strip per page; otherwise 1-4 work while the strip has focus). Switching keeps the playhead (toggle: same point / same second). |
| `JudgePair` | `v-model` 'good' / 'bad' / null, `hints`. G/B keys stay the page's job (`useQaKeys`). |
| `shared/ClipCompare` | unchanged API, retokened. Replace with `ABCompareStrip` per page (same `ClipItem` shape). |
| `shared/ModelStatus` | old, now unused (the shell uses `ui/ModelPill`). |

## Porting checklist per page
1. Wrap in `.page` + `.page-head`; call `useShortcuts` with the page's keys.
2. Swap hand-rolled buttons/chips/tags/dots/rows/toasts/confirms for the components above; replace per-component play buttons with `InlinePlay`; replace `confirm()` with `useToasts().undo` or `InlineConfirm`.
3. Scoped CSS: tokens only (no raw colours), named constants for numbers in script.
4. Page playlists: `setTransport({prev,next})` in onMounted, clear on unmount.
5. Keep text plus shape with every colour; keep `aria-pressed` / `aria-current` on toggles and current items.
