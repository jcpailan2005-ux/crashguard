'use client'

import { ReactNode, useEffect, useState } from 'react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { DetectionBox } from '@/lib/types'
import { cn } from '@/lib/utils'

type DialogActions = ReactNode | ((close: () => void) => ReactNode)

interface MediaPreviewDialogProps {
  actions?: DialogActions
  actionsClassName?: string
  compact?: boolean
  description: string
  fallbackUrl?: string | null
  mediaType: 'image' | 'video'
  mediaUrl: string | null
  onOpenChange: (open: boolean) => void
  open: boolean
  title: string
  warning?: string | null
  boxes?: DetectionBox[]
}

export function MediaPreviewDialog({
  actions,
  actionsClassName,
  compact = false,
  description,
  fallbackUrl,
  mediaType,
  mediaUrl,
  onOpenChange,
  open,
  title,
  warning,
  boxes,
}: MediaPreviewDialogProps) {
  const [videoFailed, setVideoFailed] = useState(false)
  const [naturalSize, setNaturalSize] = useState({ width: 1, height: 1 })
  const showVideoElement = mediaType === 'video' && mediaUrl && !videoFailed
  const visibleBoxes = boxes?.filter((box) => box.width > 0 && box.height > 0) ?? []
  const toPercent = (value: number, axis: 'x' | 'y') => {
    if (value <= 1) return value * 100
    return (value / (axis === 'x' ? naturalSize.width : naturalSize.height)) * 100
  }

  useEffect(() => {
    setVideoFailed(false)
  }, [mediaType, mediaUrl, open])

  const renderedActions =
    typeof actions === 'function' ? actions(() => onOpenChange(false)) : actions

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={cn(
          'border border-border bg-card',
          compact ? 'max-w-md' : 'max-w-4xl'
        )}
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {showVideoElement ? (
          <video
            key={mediaUrl}
            src={mediaUrl}
            controls
            preload="metadata"
            className={cn(
              'w-full rounded-lg bg-[var(--media-background)]',
              compact ? 'max-h-64' : 'max-h-[70vh]'
            )}
            onError={() => setVideoFailed(true)}
          >
            Your browser does not support video playback.
          </video>
        ) : !mediaUrl ? (
          <div className="space-y-4 rounded-lg border border-dashed border-border/60 bg-muted/20 p-6 text-center text-sm text-muted-foreground">
            <p>Preview is not available for this file in the current browser.</p>
            {fallbackUrl ? (
              <Button asChild variant="outline">
                <a href={fallbackUrl} target="_blank" rel="noreferrer">
                  Open Output File
                </a>
              </Button>
            ) : null}
          </div>
        ) : mediaType === 'video' ? (
          <div className="space-y-4 rounded-lg border border-dashed border-border/60 bg-muted/20 p-6 text-sm text-muted-foreground">
            <p>
              Inline video playback was not available for this file in the current browser.
            </p>
            {fallbackUrl ? (
              <Button asChild variant="outline">
                <a href={fallbackUrl} target="_blank" rel="noreferrer">
                  Open Output File
                </a>
              </Button>
            ) : null}
          </div>
        ) : (
          <div className="flex justify-center">
            <div className="relative inline-block max-w-full">
              <img
                src={mediaUrl}
                alt="Detected annotated result"
                className={cn(
                  'block max-w-full rounded-lg object-contain',
                  compact ? 'max-h-64' : 'max-h-[70vh]'
                )}
                onLoad={(event) => {
                  setNaturalSize({
                    width: event.currentTarget.naturalWidth || 1,
                    height: event.currentTarget.naturalHeight || 1,
                  })
                }}
              />
              {visibleBoxes.length > 0 ? (
                <div className="pointer-events-none absolute inset-0">
                  {visibleBoxes.map((box, index) => (
                    <div
                      key={`${box.label}-${index}`}
                      className="absolute border-2 border-[var(--status-warning)] bg-[color:var(--status-warning-bg)]/20"
                      style={{
                        left: `${toPercent(box.x, 'x')}%`,
                        top: `${toPercent(box.y, 'y')}%`,
                        width: `${toPercent(box.width, 'x')}%`,
                        height: `${toPercent(box.height, 'y')}%`,
                      }}
                    >
                      <span className="absolute left-0 top-0 max-w-full -translate-y-full truncate rounded-sm bg-[var(--status-warning)] px-1.5 py-0.5 text-[10px] font-semibold text-background">
                        {box.label} {(box.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        )}

        {(warning || (mediaType === 'video' && videoFailed)) && (
          <div className="rounded-lg border border-[var(--status-warning)] bg-[color:var(--status-warning-bg)] p-3 text-sm text-[var(--status-warning)]">
            {warning ??
              'This annotated video file exists, but this browser could not play it inline.'}
          </div>
        )}

        {renderedActions ? (
          <div
            className={cn(
              compact
                ? 'space-y-3 border-t border-border pt-4'
                : 'grid gap-2 border-t border-border pt-4 sm:grid-cols-2 lg:grid-cols-5',
              actionsClassName
            )}
          >
            {renderedActions}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
