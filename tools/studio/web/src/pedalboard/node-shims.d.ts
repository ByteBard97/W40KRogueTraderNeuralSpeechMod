// The web package has no @types/node. The pedalboard CLI and its tests run in plain Node and only need these few calls.
declare module 'node:fs' {
  export function readFileSync(path: string): Uint8Array & { buffer: ArrayBuffer; byteOffset: number; byteLength: number }
  export function readFileSync(path: string, encoding: 'utf8'): string
  export function writeFileSync(path: string, data: string | Uint8Array): void
  export function mkdtempSync(prefix: string): string
  export function existsSync(path: string): boolean
  export function readdirSync(path: string): string[]
}
declare module 'node:os' {
  export function tmpdir(): string
}
declare module 'node:path' {
  export function join(...parts: string[]): string
  export function resolve(...parts: string[]): string
  export function dirname(p: string): string
}
declare module 'node:url' {
  export function fileURLToPath(url: string): string
}
declare module 'node:child_process' {
  export interface SpawnResult {
    status: number | null
    stdout: string
    stderr: string
  }
  export function spawnSync(
    cmd: string,
    args: string[],
    opts?: { cwd?: string; encoding?: 'utf8'; timeout?: number },
  ): SpawnResult
}
declare const process: {
  argv: string[]
  exit(code?: number): never
  stdout: { write(s: string): void }
  stderr: { write(s: string): void }
}
