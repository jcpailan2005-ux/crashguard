import { AreaId } from '@/lib/locations'

export interface Sample {
  confidence: number
  description: string
  hasAccident: boolean
  id: string
  location: AreaId
  title: string
  type: 'image' | 'video'
  url: string
}

export const LOCATION_TABS = [
  { label: 'Talomo CCTV', value: 'talomo' },
  { label: 'Bago CCTV', value: 'bago' },
  { label: 'Toril CCTV', value: 'toril' },
] as const

export const SAMPLES: Sample[] = [
  {
    id: 'talomo-1',
    title: 'Talomo CCTV Footage 1',
    description: 'Traffic incident frame from Talomo camera angle 1.',
    type: 'image',
    url: '/samples/accident-01.jpg',
    hasAccident: true,
    confidence: 0.92,
    location: 'talomo',
  },
  {
    id: 'talomo-2',
    title: 'Talomo CCTV Footage 2',
    description: 'Roadside congestion and near-collision scene from Talomo.',
    type: 'image',
    url: '/samples/accident-02.jpg',
    hasAccident: true,
    confidence: 0.88,
    location: 'talomo',
  },
  {
    id: 'talomo-3',
    title: 'Talomo CCTV Footage 3',
    description: 'Multi-vehicle frame from Talomo urban crossing.',
    type: 'image',
    url: '/samples/accident-03.jpg',
    hasAccident: true,
    confidence: 0.86,
    location: 'talomo',
  },
  {
    id: 'bago-1',
    title: 'Bago CCTV Footage 1',
    description: 'Bago highway segment with normal traffic flow.',
    type: 'image',
    url: '/samples/vehicle-01.jpg',
    hasAccident: false,
    confidence: 0.18,
    location: 'bago',
  },
  {
    id: 'bago-2',
    title: 'Bago CCTV Footage 2',
    description: 'Bago intersection monitoring with vehicle-only detections.',
    type: 'image',
    url: '/samples/vehicle-02.jpg',
    hasAccident: false,
    confidence: 0.12,
    location: 'bago',
  },
  {
    id: 'bago-3',
    title: 'Bago CCTV Footage 3',
    description: 'Bago roadside stream with low-risk traffic movement.',
    type: 'image',
    url: '/samples/vehicle-03.jpg',
    hasAccident: false,
    confidence: 0.1,
    location: 'bago',
  },
  {
    id: 'toril-1',
    title: 'Toril CCTV Footage 1',
    description: 'Toril downtown frame with mixed vehicle classes.',
    type: 'image',
    url: '/samples/accident-01.jpg',
    hasAccident: true,
    confidence: 0.74,
    location: 'toril',
  },
  {
    id: 'toril-2',
    title: 'Toril CCTV Footage 2',
    description: 'Toril junction snapshot used for quick incident checks.',
    type: 'image',
    url: '/samples/vehicle-02.jpg',
    hasAccident: false,
    confidence: 0.16,
    location: 'toril',
  },
  {
    id: 'toril-3',
    title: 'Toril CCTV Footage 3',
    description: 'Toril camera feed sample with light traffic movement.',
    type: 'image',
    url: '/samples/vehicle-03.jpg',
    hasAccident: false,
    confidence: 0.09,
    location: 'toril',
  },
]
