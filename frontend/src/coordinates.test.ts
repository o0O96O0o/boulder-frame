import { describe, expect, it } from 'vitest'
import { mapPointerToNormalized, normalizedToContainPoint } from './coordinates'

describe('mapPointerToNormalized', () => {
  it('maps a 16:9 source in a square letterboxed panel', () => {
    expect(mapPointerToNormalized(50, 200, { left: 0, top: 0, width: 400, height: 400 }, 1600, 900)).toEqual({ x: 0.125, y: 0.5 })
    expect(mapPointerToNormalized(200, 200, { left: 0, top: 0, width: 400, height: 400 }, 1600, 900)).toEqual({ x: 0.5, y: 0.5 })
  })
  it('maps portrait media with horizontal letterboxing and offsets', () => {
    const point = mapPointerToNormalized(250, 100, { left: 100, top: 50, width: 300, height: 500 }, 1080, 1920)
    expect(point?.x).toBeCloseTo(0.5)
    expect(point?.y).toBeCloseTo(0.1)
    expect(mapPointerToNormalized(105, 100, { left: 100, top: 50, width: 300, height: 500 }, 1080, 1920)).toBeNull()
  })
  it('returns source edges and rejects invalid dimensions', () => {
    expect(mapPointerToNormalized(100, 50, { left: 100, top: 50, width: 300, height: 200 }, 300, 200)).toEqual({ x: 0, y: 0 })
    expect(mapPointerToNormalized(0, 0, { left: 0, top: 0, width: 0, height: 200 }, 300, 200)).toBeNull()
  })
})

it('maps normalized source coordinates back into a letterboxed display', () => {
  expect(normalizedToContainPoint({ x: 0.5, y: 0.5 }, 400, 400, 1600, 900)).toEqual({ x: 0.5, y: 0.5 })
  expect(normalizedToContainPoint({ x: 0, y: 0 }, 400, 400, 1600, 900)).toEqual({ x: 0, y: 0.21875 })
})
