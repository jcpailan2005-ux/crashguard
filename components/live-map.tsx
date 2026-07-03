'use client'

import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

import { APP_CONFIG } from '@/lib/app-config'
import { CrashCase } from '@/lib/types'

interface LiveMapProps {
  cases: CrashCase[]
  selectedCase: CrashCase | null
}

const AccidentIcon = L.icon({
  iconUrl: APP_CONFIG.map.accidentMarkerUrl,
  shadowUrl: APP_CONFIG.map.markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

const SafeIcon = L.icon({
  iconUrl: APP_CONFIG.map.safeMarkerUrl,
  shadowUrl: APP_CONFIG.map.markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
})

const DEFAULT_CENTER: [number, number] = [
  APP_CONFIG.map.defaultCenter.latitude,
  APP_CONFIG.map.defaultCenter.longitude,
]
const PHILIPPINES_BOUNDS = L.latLngBounds([4.6, 116.7], [21.2, 126.6])

function popupContent(caseItem: CrashCase) {
  return `
    <div class="text-sm">
      <p class="font-semibold">${caseItem.caseId}</p>
      <p>${caseItem.location.label}</p>
      <p class="text-xs">${caseItem.status.replaceAll('_', ' ')}</p>
      <p class="text-xs">${(caseItem.confidence * 100).toFixed(1)}% confidence</p>
      ${
        caseItem.location.isFallback
          ? '<p class="text-xs font-medium">Fallback coordinates</p>'
          : ''
      }
    </div>
  `
}

export default function LiveMap({ cases, selectedCase }: LiveMapProps) {
  const mapRef = useRef<L.Map | null>(null)
  const markersRef = useRef<L.Marker[]>([])

  useEffect(() => {
    if (!mapRef.current) {
      mapRef.current = L.map('map', {
        maxBounds: PHILIPPINES_BOUNDS,
        maxBoundsViscosity: 1.0,
      }).setView(DEFAULT_CENTER, 11)

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(mapRef.current)
    }
  }, [])

  useEffect(() => {
    if (!mapRef.current) return

    markersRef.current.forEach((marker) => marker.removeFrom(mapRef.current!))
    markersRef.current = []

    cases.forEach((caseItem) => {
      const icon = caseItem.status === 'false_alarm' ? SafeIcon : AccidentIcon
      const marker = L.marker(
        [caseItem.location.latitude, caseItem.location.longitude],
        { icon }
      ).addTo(mapRef.current!)

      marker.bindPopup(popupContent(caseItem))
      markersRef.current.push(marker)

      if (selectedCase?.caseId === caseItem.caseId) {
        marker.openPopup()
      }
    })

    if (selectedCase) {
      mapRef.current.setView(
        [selectedCase.location.latitude, selectedCase.location.longitude],
        14,
        { animate: true }
      )
    } else if (cases.length > 0) {
      const bounds = L.latLngBounds(
        cases.map((caseItem) => [
          caseItem.location.latitude,
          caseItem.location.longitude,
        ])
      )
      mapRef.current.fitBounds(bounds.pad(0.2), { maxZoom: 14 })
    }
  }, [cases, selectedCase])

  return <div id="map" className="relative z-0 h-full w-full" />
}
