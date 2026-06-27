import crypto from 'node:crypto'
import fs from 'node:fs'

const args = new Set(process.argv.slice(2))
const getArg = (name) => {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

const useEmulator = args.has('--emulator')
const cleanup = args.has('--cleanup')
const cleanupUid = getArg('--uid')
const cleanupUserUid = getArg('--user-uid')
const cleanupResponderUid = getArg('--responder-uid')
const cleanupAdminUid = getArg('--admin-uid') || cleanupUid

const env = fs.existsSync('.env.local')
  ? Object.fromEntries(
      fs
        .readFileSync('.env.local', 'utf8')
        .split(/\r?\n/)
        .filter((line) => line.includes('=') && !line.trim().startsWith('#'))
        .map((line) => {
          const index = line.indexOf('=')
          return [line.slice(0, index).trim(), line.slice(index + 1).trim()]
        })
    )
  : {}

const apiKey = env.NEXT_PUBLIC_FIREBASE_API_KEY || 'qa-emulator-key'
const projectId = env.NEXT_PUBLIC_FIREBASE_PROJECT_ID || 'crashguard-qa'
const authEmulatorHost =
  env.NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST ||
  process.env.FIREBASE_AUTH_EMULATOR_HOST ||
  'localhost:9099'
const firestoreEmulatorHost =
  env.NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST ||
  process.env.FIRESTORE_EMULATOR_HOST ||
  'localhost:8080'

const qaStatuses = [
  'pending_review',
  'under_review',
  'confirmed_crash',
  'false_alarm',
  'dispatched',
  'resolved',
]

function loadServiceAccount() {
  if (useEmulator) return null

  if (process.env.FIREBASE_SERVICE_ACCOUNT_JSON) {
    return JSON.parse(process.env.FIREBASE_SERVICE_ACCOUNT_JSON)
  }

  const credentialsPath =
    process.env.GOOGLE_APPLICATION_CREDENTIALS ||
    process.env.FIREBASE_SERVICE_ACCOUNT_PATH

  if (!credentialsPath) {
    throw new Error(
      'Set GOOGLE_APPLICATION_CREDENTIALS, FIREBASE_SERVICE_ACCOUNT_PATH, FIREBASE_SERVICE_ACCOUNT_JSON, or use --emulator.'
    )
  }

  return JSON.parse(fs.readFileSync(credentialsPath, 'utf8'))
}

function base64url(input) {
  return Buffer.from(input)
    .toString('base64')
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replaceAll('=', '')
}

async function getAccessToken(serviceAccount) {
  if (useEmulator) return 'owner'

  const now = Math.floor(Date.now() / 1000)
  const header = { alg: 'RS256', typ: 'JWT' }
  const claim = {
    iss: serviceAccount.client_email,
    scope:
      'https://www.googleapis.com/auth/datastore https://www.googleapis.com/auth/cloud-platform',
    aud: 'https://oauth2.googleapis.com/token',
    exp: now + 3600,
    iat: now,
  }
  const unsigned = `${base64url(JSON.stringify(header))}.${base64url(
    JSON.stringify(claim)
  )}`
  const signature = crypto
    .createSign('RSA-SHA256')
    .update(unsigned)
    .sign(serviceAccount.private_key)
  const assertion = `${unsigned}.${base64url(signature)}`

  const response = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion,
    }),
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.error_description || data.error || 'Could not get access token.')
  }
  return data.access_token
}

function authBaseUrl() {
  return useEmulator
    ? `http://${authEmulatorHost}/identitytoolkit.googleapis.com/v1`
    : 'https://identitytoolkit.googleapis.com/v1'
}

function firestoreBaseUrl() {
  return useEmulator
    ? `http://${firestoreEmulatorHost}/v1/projects/${projectId}/databases/(default)/documents`
    : `https://firestore.googleapis.com/v1/projects/${projectId}/databases/(default)/documents`
}

async function createAuthUser(label = 'qa') {
  const email = `crashguard.${label}.${Date.now()}@example.com`
  const password = `Qa!${crypto.randomBytes(9).toString('base64url')}9`
  const response = await fetch(`${authBaseUrl()}/accounts:signUp?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, returnSecureToken: true }),
  })
  const data = await response.json()
  if (!response.ok) {
    throw new Error(data.error?.message || 'Could not create Firebase Auth user.')
  }
  return { email, password, uid: data.localId, idToken: data.idToken }
}

async function deleteAuthUser(uid) {
  if (!useEmulator) {
    console.warn('Skipping Auth cleanup for production; use Firebase Admin tooling if needed.')
    return
  }

  const response = await fetch(`${authBaseUrl()}/accounts:delete?key=${apiKey}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ localId: uid }),
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    console.warn(`Auth emulator cleanup warning: ${data.error?.message || response.statusText}`)
  }
}

function value(input) {
  if (input === undefined) return { nullValue: null }
  if (input === null) return { nullValue: null }
  if (Array.isArray(input)) return { arrayValue: { values: input.map(value) } }
  if (typeof input === 'boolean') return { booleanValue: input }
  if (typeof input === 'number') return { doubleValue: input }
  if (typeof input === 'object') {
    return {
      mapValue: {
        fields: Object.fromEntries(
          Object.entries(input).map(([key, nestedValue]) => [key, value(nestedValue)])
        ),
      },
    }
  }
  return { stringValue: String(input) }
}

async function patchDocument(accessToken, path, data) {
  const response = await fetch(`${firestoreBaseUrl()}/${path}`, {
    method: 'PATCH',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      fields: Object.fromEntries(
        Object.entries(data).map(([key, fieldValue]) => [key, value(fieldValue)])
      ),
    }),
  })
  const responseData = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(responseData.error?.message || `Could not write ${path}.`)
  }
  return responseData
}

async function deleteDocument(accessToken, path) {
  const response = await fetch(`${firestoreBaseUrl()}/${path}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${accessToken}` },
  })

  if (!response.ok && response.status !== 404) {
    const data = await response.json().catch(() => ({}))
    console.warn(`Cleanup warning for ${path}: ${data.error?.message || response.statusText}`)
  }
}

function caseData(status, index, uid) {
  const baseTimeMs = Date.now() - (index + 1) * 15 * 60 * 1000
  const iso = new Date(baseTimeMs).toISOString()
  const acknowledgedAt =
    status === 'pending_review' ? null : new Date(baseTimeMs + 2 * 60 * 1000).toISOString()
  const confirmedAt =
    status === 'confirmed_crash' || status === 'dispatched' || status === 'resolved'
      ? new Date(baseTimeMs + 5 * 60 * 1000).toISOString()
      : null
  const falseAlarmAt =
    status === 'false_alarm' ? new Date(baseTimeMs + 5 * 60 * 1000).toISOString() : null
  const dispatchedAt =
    status === 'dispatched' || status === 'resolved'
      ? new Date(baseTimeMs + 9 * 60 * 1000).toISOString()
      : null
  const resolvedAt =
    status === 'resolved' ? new Date(baseTimeMs + 14 * 60 * 1000).toISOString() : null
  const latestLifecycleAt =
    resolvedAt || dispatchedAt || confirmedAt || falseAlarmAt || acknowledgedAt || iso
  const caseId = `QA-${status.toUpperCase()}-${index}`
  const previous =
    status === 'pending_review'
      ? 'pending_review'
      : status === 'under_review'
        ? 'pending_review'
        : status === 'confirmed_crash'
          ? 'under_review'
          : status === 'false_alarm'
            ? 'under_review'
            : status === 'dispatched'
              ? 'confirmed_crash'
              : 'dispatched'
  const action =
    status === 'pending_review'
      ? 'review_alert'
      : status === 'under_review'
        ? 'review_alert'
        : status === 'confirmed_crash'
          ? 'confirm_crash'
          : status === 'false_alarm'
            ? 'mark_false_alarm'
            : status === 'dispatched'
              ? 'dispatch_help'
              : 'resolve_case'

  return {
    areaId: index % 2 === 0 ? 'talomo' : 'bago',
    caseId,
    detectionId: `DET-${caseId}`,
    status,
    triggerStatus: 'sample_detection',
    reviewerId: status === 'pending_review' ? null : uid,
    user: {
      name: `QA Driver ${index}`,
      phone: `09${String(100000000 + index).padStart(9, '0')}`,
      email: `driver${index}@example.com`,
    },
    vehicle: {
      plateNumber: `QA-${1000 + index}`,
      type: index % 2 === 0 ? 'Sedan' : 'SUV',
      color: index % 2 === 0 ? 'White' : 'Blue',
      description: 'Seeded QA vehicle',
    },
    location: {
      label: index === 5 ? 'QA Fallback Location' : `QA ${status.replaceAll('_', ' ')}`,
      latitude: index === 5 ? 7.1907 : 7.0667 + index * 0.01,
      longitude: index === 5 ? 125.4553 : 125.5833 + index * 0.01,
      areaId: index % 2 === 0 ? 'talomo' : 'bago',
      isFallback: index === 5,
    },
    media: {
      mediaType: index % 2 === 0 ? 'image' : 'video',
      source: 'sample',
      sourceFile: `/samples/${index % 2 === 0 ? 'accident-01.jpg' : 'accident-02.jpg'}`,
      annotatedMediaUrl: null,
      annotatedMediaDownloadUrl: null,
      annotatedKeyFrameUrl: null,
    },
    confidence: 0.72 + index * 0.03,
    notes: status === 'resolved' ? 'QA resolved case notes.' : '',
    actions: [
      {
        action,
        actorId: status === 'pending_review' ? 'system' : uid,
        timestamp: latestLifecycleAt,
        notes: `Seeded ${status} case.`,
        previousStatus: previous,
        nextStatus: status,
      },
    ],
    acknowledgedAt,
    confirmedAt,
    createdAt: iso,
    detectedAt: iso,
    dispatchedAt,
    falseAlarmAt,
    resolvedAt,
    updatedAt: latestLifecycleAt,
    accidentDetected: true,
    detections: [
      {
        label: 'accident',
        score: 0.72 + index * 0.03,
        box: [80 + index * 10, 100, 240, 280],
      },
    ],
  }
}

async function seed(accessToken) {
  const normalUser = await createAuthUser('user')
  const responder = await createAuthUser('responder')
  const admin = await createAuthUser('admin')
  const iso = new Date().toISOString()

  await patchDocument(accessToken, `users/${normalUser.uid}`, {
    active: true,
    areaId: null,
    createdAt: iso,
    displayName: 'QA Normal User',
    email: normalUser.email,
    role: 'user',
    uid: normalUser.uid,
    updatedAt: iso,
  })

  await patchDocument(accessToken, `users/${responder.uid}`, {
    active: true,
    areaId: 'talomo',
    createdAt: iso,
    displayName: 'QA Talomo Responder',
    email: responder.email,
    role: 'responder',
    uid: responder.uid,
    updatedAt: iso,
  })

  await patchDocument(accessToken, `users/${admin.uid}`, {
    active: true,
    areaId: null,
    createdAt: iso,
    displayName: 'QA Admin',
    email: admin.email,
    role: 'admin',
    uid: admin.uid,
    updatedAt: iso,
  })

  for (const [index, status] of qaStatuses.entries()) {
    const data = caseData(status, index, responder.uid)
    await patchDocument(accessToken, `incidents/${data.caseId}`, data)
    await patchDocument(accessToken, `notifications/NOT-${data.caseId}`, {
      areaId: data.areaId,
      incident_id: data.caseId,
      title: `QA ${status.replaceAll('_', ' ')} review`,
      message: `Seeded QA review notification for ${data.caseId}.`,
      timestamp: data.updatedAt,
      alertLevel: 'review',
      read: false,
      responderUid: responder.uid,
    })
  }

  return { normalUser, responder, admin }
}

async function cleanupQa(accessToken, userUid, responderUid, adminUid) {
  if (!userUid && !responderUid && !adminUid) {
    throw new Error('Cleanup requires --uid <QA_ADMIN_UID>, --user-uid <QA_USER_UID>, --responder-uid <QA_RESPONDER_UID>, or --admin-uid <QA_ADMIN_UID>.')
  }

  for (const [index, status] of qaStatuses.entries()) {
    const caseId = `QA-${status.toUpperCase()}-${index}`
    await deleteDocument(accessToken, `notifications/NOT-${caseId}`)
    await deleteDocument(accessToken, `incidents/${caseId}`)
  }
  if (userUid) {
    await deleteDocument(accessToken, `users/${userUid}`)
    await deleteAuthUser(userUid)
  }

  if (responderUid && responderUid !== userUid) {
    await deleteDocument(accessToken, `users/${responderUid}`)
    await deleteAuthUser(responderUid)
  }

  if (adminUid && adminUid !== userUid && adminUid !== responderUid) {
    await deleteDocument(accessToken, `users/${adminUid}`)
    await deleteAuthUser(adminUid)
  }
}

async function main() {
  if (!apiKey || !projectId) {
    throw new Error('Firebase API key and project ID are required.')
  }

  const serviceAccount = loadServiceAccount()
  const accessToken = await getAccessToken(serviceAccount)

  if (cleanup) {
    await cleanupQa(accessToken, cleanupUserUid, cleanupResponderUid, cleanupAdminUid)
    console.log(
      JSON.stringify(
        {
          cleanup: true,
          emulator: useEmulator,
          userUid: cleanupUserUid ?? null,
          responderUid: cleanupResponderUid ?? null,
          adminUid: cleanupAdminUid ?? null,
        },
        null,
        2
      )
    )
    return
  }

  const { normalUser, responder, admin } = await seed(accessToken)
  console.log(
    JSON.stringify(
      {
        emulator: useEmulator,
        accounts: {
          user: {
            email: normalUser.email,
            password: normalUser.password,
            uid: normalUser.uid,
            role: 'user',
          },
          responder: {
            email: responder.email,
            password: responder.password,
            uid: responder.uid,
            role: 'responder',
          },
          admin: {
            email: admin.email,
            password: admin.password,
            uid: admin.uid,
            role: 'admin',
          },
        },
        statuses: qaStatuses,
      },
      null,
      2
    )
  )
}

main().catch((error) => {
  console.error(error.message)
  process.exit(1)
})
