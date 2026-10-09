import { describe, expect, it } from 'vitest'
import { fileUrl } from './fileUrl'

describe('fileUrl', () => {
  it('encodes the path', () => expect(fileUrl('data/a b/x.wav')).toBe('/file?p=data%2Fa%20b%2Fx.wav'))
  it('turns a ?v= cache buster into a query param', () =>
    expect(fileUrl('data/studio/p/fx/t1.wav?v=77')).toBe('/file?p=data%2Fstudio%2Fp%2Ffx%2Ft1.wav&v=77'))
})
