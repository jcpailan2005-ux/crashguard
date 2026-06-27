# Firebase Emulator QA Setup

This setup is for local QA only. It does not weaken production Firestore rules.

## Environment

Set these in `.env.local` when using emulators:

```powershell
NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true
NEXT_PUBLIC_FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
NEXT_PUBLIC_FIRESTORE_EMULATOR_HOST=localhost:8080
```

Keep the normal `NEXT_PUBLIC_FIREBASE_*` project values set. The app still needs them to initialize Firebase, but reads/writes are redirected to local emulators.

## Start Emulators

Install/use Firebase CLI, then run:

```powershell
firebase emulators:start --only auth,firestore
```

## Seed QA Data

```powershell
node scripts/seed-firestore-qa.mjs --emulator
```

The script prints the generated QA admin email and password.

## Cleanup QA Data

Use the UID printed by the seed command:

```powershell
node scripts/seed-firestore-qa.mjs --emulator --cleanup --uid <QA_UID>
```

Production seeding requires a service account:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\service-account.json"
node scripts/seed-firestore-qa.mjs
```
