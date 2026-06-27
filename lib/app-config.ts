import { APP_LOCATIONS } from '@/lib/locations'

export const APP_CONFIG = {
  backendUrl:
    process.env.NEXT_PUBLIC_BACKEND_URL?.replace(/\/+$/, '') ||
    'http://localhost:8000',
  useMockData: process.env.NEXT_PUBLIC_USE_MOCK_DATA === 'true',
  detection: {
    meaningfulConfidenceThreshold: Number(
      process.env.NEXT_PUBLIC_MEANINGFUL_CONFIDENCE_THRESHOLD ?? 0.3
    ),
    alertDebounceMs: Number(process.env.NEXT_PUBLIC_ALERT_DEBOUNCE_MS ?? 4500),
    duplicateHistoryWindowMs: Number(
      process.env.NEXT_PUBLIC_DUPLICATE_HISTORY_WINDOW_MS ?? 8000
    ),
    liveSessionPublishIntervalMs: Number(
      process.env.NEXT_PUBLIC_LIVE_SESSION_PUBLISH_INTERVAL_MS ?? 3000
    ),
    responderAlertDebounceMs: Number(
      process.env.NEXT_PUBLIC_RESPONDER_ALERT_DEBOUNCE_MS ?? 10000
    ),
  },
  map: {
    markerShadowUrl:
      process.env.NEXT_PUBLIC_MAP_MARKER_SHADOW_URL ||
      'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
    accidentMarkerUrl:
      process.env.NEXT_PUBLIC_MAP_ACCIDENT_MARKER_URL ||
      'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-red.png',
    safeMarkerUrl:
      process.env.NEXT_PUBLIC_MAP_SAFE_MARKER_URL ||
      'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-green.png',
    defaultCenter: APP_LOCATIONS.talomo.coordinates,
  },
}
