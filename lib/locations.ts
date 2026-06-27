export type AreaId = 'talomo' | 'bago' | 'toril'

export interface AppLocation {
  areaId: AreaId
  label: string
  coordinates: {
    latitude: number
    longitude: number
  }
}

export const FALLBACK_LOCATION: AppLocation = {
  areaId: 'talomo',
  label: 'Fallback Demo Location',
  coordinates: {
    latitude: 7.1907,
    longitude: 125.4553,
  },
}

export const APP_LOCATIONS: Record<AreaId, AppLocation> = {
  talomo: {
    areaId: 'talomo',
    label: 'Talomo',
    coordinates: {
      latitude: 7.0667,
      longitude: 125.5833,
    },
  },
  bago: {
    areaId: 'bago',
    label: 'Bago Aplaya',
    coordinates: {
      latitude: 7.0498,
      longitude: 125.611,
    },
  },
  toril: {
    areaId: 'toril',
    label: 'Toril',
    coordinates: {
      latitude: 7.0172,
      longitude: 125.5046,
    },
  },
}

export function getAreaLabel(areaId?: string | null) {
  if (areaId === 'talomo' || areaId === 'bago' || areaId === 'toril') {
    return APP_LOCATIONS[areaId].label
  }

  return FALLBACK_LOCATION.label
}

export function getAreaCoordinates(areaId?: string | null) {
  if (areaId === 'talomo' || areaId === 'bago' || areaId === 'toril') {
    return {
      ...APP_LOCATIONS[areaId].coordinates,
      isFallback: false,
    }
  }

  return {
    ...FALLBACK_LOCATION.coordinates,
    isFallback: true,
  }
}
