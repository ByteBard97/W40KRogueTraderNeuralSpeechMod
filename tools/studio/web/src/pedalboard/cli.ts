// Command line front for the generator, so Python tests and tools can use it:
//   npx vite-node src/pedalboard/cli.ts -- <graph.json> [--catalog <path>] [--lib <path>]
// Prints {code, controls, params} as JSON; exits 1 with the issues on stderr when the graph is invalid.
import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { generate, paramsFor } from './generate'
import { GraphError } from './types'
import type { Catalog, Graph } from './types'

const FX_FAUST_DIR = resolve(dirname(fileURLToPath(import.meta.url)), '../../../../fx_lab/faust')
const EXIT_INVALID = 1
const EXIT_USAGE = 2

function parseArgs(argv: string[]): { graph?: string; catalog: string; lib: string } {
  const args = argv.filter((a) => a !== '--')
  const out = { graph: undefined as string | undefined, catalog: resolve(FX_FAUST_DIR, 'catalog.json'), lib: resolve(FX_FAUST_DIR, 'blocks.lib') }
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--catalog') out.catalog = resolve(args[++i])
    else if (args[i] === '--lib') out.lib = resolve(args[++i])
    else out.graph = resolve(args[i])
  }
  return out
}

function main(): void {
  const a = parseArgs(process.argv.slice(2))
  if (!a.graph) {
    process.stderr.write('usage: cli.ts <graph.json> [--catalog <path>] [--lib <path>]\n')
    process.exit(EXIT_USAGE)
  }
  const graph = JSON.parse(readFileSync(a.graph, 'utf8')) as Graph
  const catalog = JSON.parse(readFileSync(a.catalog, 'utf8')) as Catalog
  try {
    const { code, controls } = generate(graph, catalog, readFileSync(a.lib, 'utf8'))
    process.stdout.write(JSON.stringify({ code, controls, params: paramsFor(graph, catalog) }))
  } catch (e) {
    if (!(e instanceof GraphError)) throw e
    process.stderr.write(JSON.stringify(e.issues, null, 1) + '\n')
    process.exit(EXIT_INVALID)
  }
}

main()
