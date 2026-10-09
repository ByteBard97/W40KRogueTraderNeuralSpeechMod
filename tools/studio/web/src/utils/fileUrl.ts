export function fileUrl(path: string): string {
  const [p, v] = path.split('?')
  return `/file?p=${encodeURIComponent(p)}${v ? `&${v}` : ''}`
}
