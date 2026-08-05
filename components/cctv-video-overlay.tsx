'use client'

import { ReactNode, useEffect, useMemo, useRef, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { DetectionBox } from '@/lib/types'

interface CctvVideoOverlayProps {
  annotatedPreviewUrl?: string | null
  boxes?: DetectionBox[]
  boxFit?: 'contain' | 'cover'
  children: ReactNode
  emptyDetectionLabel?: string
  isDetecting: boolean
  isLive: boolean
  labels: string[]
  sourceHeight?: number | null
  sourceWidth?: number | null
  timestamp: string
}

type ContainerSize = {
  width: number
  height: number
}

function getBoxBounds(boxes: DetectionBox[]) {
  return boxes.reduce(
    (bounds, box) => ({
      width: Math.max(bounds.width, box.x + box.width),
      height: Math.max(bounds.height, box.y + box.height),
    }),
    { width: 0, height: 0 }
  )
}

export function CctvVideoOverlay({
  annotatedPreviewUrl,
  boxes = [],
  boxFit = 'contain',
  children,
  emptyDetectionLabel = 'No detection in current frame',
  isDetecting,
  isLive,
  labels,
  sourceHeight,
  sourceWidth,
  timestamp,
}: CctvVideoOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerSize, setContainerSize] = useState<ContainerSize>({
    width: 0,
    height: 0,
  })

  useEffect(() => {
    const element = containerRef.current
    if (!element) {
      return
    }

    const updateSize = () => {
      setContainerSize({
        width: element.clientWidth,
        height: element.clientHeight,
      })
    }

    updateSize()

    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', updateSize)
      return () => window.removeEventListener('resize', updateSize)
    }

    const observer = new ResizeObserver(updateSize)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  const visibleBoxes = useMemo(
    () =>
      boxes.filter(
        (box) =>
          Number.isFinite(box.x) &&
          Number.isFinite(box.y) &&
          Number.isFinite(box.width) &&
          Number.isFinite(box.height) &&
          box.width > 0 &&
          box.height > 0
      ),
    [boxes]
  )

  const boxBounds = useMemo(() => getBoxBounds(visibleBoxes), [visibleBoxes])
  const hasNormalizedBoxes =
    visibleBoxes.length > 0 &&
    visibleBoxes.every((box) => box.x + box.width <= 1.01 && box.y + box.height <= 1.01)
  const resolvedSourceWidth =
    sourceWidth && sourceWidth > 0
      ? sourceWidth
      : hasNormalizedBoxes
        ? 1
        : boxBounds.width
  const resolvedSourceHeight =
    sourceHeight && sourceHeight > 0
      ? sourceHeight
      : hasNormalizedBoxes
        ? 1
        : boxBounds.height

  const mediaRect = useMemo(() => {
    if (
      containerSize.width <= 0 ||
      containerSize.height <= 0 ||
      resolvedSourceWidth <= 0 ||
      resolvedSourceHeight <= 0
    ) {
      return null
    }

    const scale =
      boxFit === 'cover'
        ? Math.max(
            containerSize.width / resolvedSourceWidth,
            containerSize.height / resolvedSourceHeight
          )
        : Math.min(
            containerSize.width / resolvedSourceWidth,
            containerSize.height / resolvedSourceHeight
          )
    const width = resolvedSourceWidth * scale
    const height = resolvedSourceHeight * scale

    return {
      left: (containerSize.width - width) / 2,
      top: (containerSize.height - height) / 2,
      width,
      height,
    }
  }, [
    boxFit,
    containerSize.height,
    containerSize.width,
    resolvedSourceHeight,
    resolvedSourceWidth,
  ])

  return (
    <div
      ref={containerRef}
      className="relative aspect-video overflow-hidden bg-[var(--media-background)]"
    >
      {children}

      {mediaRect && visibleBoxes.length > 0 && (
        <div
          className="pointer-events-none absolute"
          style={{
            height: mediaRect.height,
            left: mediaRect.left,
            top: mediaRect.top,
            width: mediaRect.width,
          }}
        >
          {visibleBoxes.map((box, index) => {
            const left = (box.x / resolvedSourceWidth) * 100
            const top = (box.y / resolvedSourceHeight) * 100
            const width = (box.width / resolvedSourceWidth) * 100
            const height = (box.height / resolvedSourceHeight) * 100
            const confidence = Number.isFinite(box.confidence)
              ? Math.max(0, Math.min(1, box.confidence))
              : null

            return (
              <div
                key={`${box.label}-${box.x}-${box.y}-${index}`}
                className="absolute rounded-sm border-2 border-red-500 bg-red-500/10 shadow-[0_0_0_1px_rgba(0,0,0,0.35)]"
                style={{
                  height: `${height}%`,
                  left: `${left}%`,
                  top: `${top}%`,
                  width: `${width}%`,
                }}
              >
                <div className="absolute left-0 top-0 max-w-full -translate-y-full rounded-sm bg-red-600 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-white shadow-sm">
                  <span className="block truncate capitalize">
                    {box.label || 'detection'}
                    {confidence != null ? ` ${(confidence * 100).toFixed(0)}%` : ''}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}

      <div className="pointer-events-none absolute left-4 top-4 rounded-md border border-[var(--media-border)] bg-[color:var(--media-overlay)] px-3 py-2 text-xs font-mono text-[var(--media-foreground)] shadow-lg backdrop-blur-sm">
        {timestamp}
      </div>

      <div className="pointer-events-none absolute right-4 top-4 flex items-center gap-2">
        {isLive && (
          <Badge className="border-[var(--status-live)] bg-[color:var(--status-live-bg)] text-[var(--status-live)] hover:bg-[color:var(--status-live-bg)]">
            LIVE
          </Badge>
        )}
        {isDetecting && (
          <Badge className="bg-primary/90 text-primary-foreground hover:bg-primary/90">
            SCANNING
          </Badge>
        )}
      </div>

      {labels.length > 0 && (
        <div className="pointer-events-none absolute bottom-4 left-4 flex max-w-[60%] flex-wrap gap-2">
          {labels.slice(0, 4).map((label, index) => (
            <Badge
              key={`${label}-${index}`}
              variant="outline"
              className="border-[var(--media-border)] bg-[color:var(--media-overlay)] capitalize text-[var(--media-foreground)]"
            >
              {label}
            </Badge>
          ))}
        </div>
      )}

      {isDetecting && labels.length === 0 && (
        <div className="pointer-events-none absolute bottom-4 left-4">
          <Badge
            variant="outline"
            className="border-[var(--media-border)] bg-[color:var(--media-overlay)] text-[var(--media-foreground)]"
          >
            {emptyDetectionLabel}
          </Badge>
        </div>
      )}

      {annotatedPreviewUrl && (
        <div className="pointer-events-none absolute bottom-4 right-4 h-28 w-44 overflow-hidden rounded-lg border border-[var(--media-border)] bg-[color:var(--media-overlay)] shadow-xl backdrop-blur-sm sm:h-32 sm:w-52">
          <img
            src={annotatedPreviewUrl}
            alt="Latest annotated detection preview"
            className="h-full w-full object-cover"
          />
        </div>
      )}
    </div>
  )
}
