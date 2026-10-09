export function fileUrl(path: string): string {
  const [p, v] = path.split('?')
  return `/file?p=${encodeURIComponent(p)}${v ? `&${v}` : ''}`
}

/** Compressed copy of a wav, from the studio's /fx-file route. */
export function fxUrl(path: string, fx: string): string {
  return `/fx-file?p=${encodeURIComponent(path)}&fx=${encodeURIComponent(fx)}`
}
