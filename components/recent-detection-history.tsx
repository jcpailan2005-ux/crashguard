'use client'

import { Badge } from '@/components/ui/badge'
import { Card } from '@/components/ui/card'

export interface DetectionHistoryEntry {
  accidentDetected: boolean
  confidence: number
  id: string
  labels: string[]
  timestamp: string
}

interface RecentDetectionHistoryProps {
  entries: DetectionHistoryEntry[]
}

export function RecentDetectionHistory({
  entries,
}: RecentDetectionHistoryProps) {
  if (entries.length === 0) {
    return null
  }

  return (
    <Card className="border border-border">
      <div className="border-b border-border p-4">
        <h3 className="text-lg font-semibold">Recent Detection History</h3>
        <p className="text-sm text-muted-foreground">
          Only meaningful live detections are listed here.
        </p>
      </div>

      <div className="space-y-3 p-4">
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="flex flex-col gap-3 rounded border border-border/50 bg-card/50 p-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="truncate font-medium">
                {entry.labels.join(', ')}
              </p>
              <p className="min-w-[10ch] whitespace-nowrap font-mono text-sm text-muted-foreground tabular-nums">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </p>
            </div>

            <div className="flex items-center gap-3 sm:flex-none">
              <Badge
                variant="outline"
                className="min-w-[5.5rem] justify-center font-mono tabular-nums"
              >
                {(entry.confidence * 100).toFixed(0)}%
              </Badge>

              <Badge
                className={
                  entry.accidentDetected
                    ? 'min-w-[6.5rem] justify-center border-destructive/50 bg-destructive/20 text-destructive'
                    : 'min-w-[6.5rem] justify-center border-[var(--status-resolved)] bg-[color:var(--status-resolved-bg)] text-[var(--status-resolved)]'
                }
                variant="outline"
              >
                {entry.accidentDetected ? 'Possible crash' : 'No crash flagged'}
              </Badge>
            </div>
          </div>
        ))}
      </div>
    </Card>
  )
}
