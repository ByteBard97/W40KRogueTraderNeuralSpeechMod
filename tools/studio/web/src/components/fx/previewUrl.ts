/** Separator the server's /fx-render route uses between chained presets. */
export const PREVIEW_SEP = '|'

/** URL of a wav with the preset chain applied. Blank `path` means the server's default Pasqal sample. */
export function fxRenderUrl(chain: string[], path = ''): string {
  const q = new URLSearchParams({ presets: chain.join(PREVIEW_SEP) })
  if (path) q.set('p', path)
  return `/fx-render?${q.toString()}`
}

/** Player id for a rendered chain; `?` marks a query so the shared player keeps it as a plain key. */
export const fxPreviewId = (chain: string[], path = '') => `fx-render:${chain.join(PREVIEW_SEP)}:${path}`
