/** Runs async jobs one after another per key, so writes for the same row reach the server in click order. */
export function createKeyedQueue() {
  const tails = new Map<string, Promise<unknown>>()
  return function enqueue<T>(key: string, job: () => Promise<T>): Promise<T> {
    const run = (tails.get(key) ?? Promise.resolve()).then(job, job)
    const tail = run.catch(() => undefined)
    tails.set(key, tail)
    void tail.then(() => { if (tails.get(key) === tail) tails.delete(key) })
    return run
  }
}
