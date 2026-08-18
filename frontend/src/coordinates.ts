export interface Rect { left: number; top: number; width: number; height: number }
export interface NormalizedPoint { x: number; y: number }

export function normalizedToContainPoint(point: NormalizedPoint, mediaWidth: number, mediaHeight: number, sourceWidth: number, sourceHeight: number): NormalizedPoint {
  const scale = Math.min(mediaWidth / sourceWidth, mediaHeight / sourceHeight)
  const renderedWidth = sourceWidth * scale
  const renderedHeight = sourceHeight * scale
  return {
    x: ((mediaWidth - renderedWidth) / 2 + point.x * renderedWidth) / mediaWidth,
    y: ((mediaHeight - renderedHeight) / 2 + point.y * renderedHeight) / mediaHeight,
  }
}

/** Maps a pointer in a contain-rendered media element into source-frame coordinates. */
export function mapPointerToNormalized(pointerX: number, pointerY: number, mediaRect: Rect, sourceWidth: number, sourceHeight: number): NormalizedPoint | null {
  if (sourceWidth <= 0 || sourceHeight <= 0 || mediaRect.width <= 0 || mediaRect.height <= 0) return null
  const scale = Math.min(mediaRect.width / sourceWidth, mediaRect.height / sourceHeight)
  const rendered = { width: sourceWidth * scale, height: sourceHeight * scale }
  const offset = { x: (mediaRect.width - rendered.width) / 2, y: (mediaRect.height - rendered.height) / 2 }
  const x = (pointerX - mediaRect.left - offset.x) / rendered.width
  const y = (pointerY - mediaRect.top - offset.y) / rendered.height
  if (x < 0 || x > 1 || y < 0 || y > 1) return null
  return { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) }
}
