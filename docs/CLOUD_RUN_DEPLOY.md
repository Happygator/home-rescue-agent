# Deploy: Cloud Run + Firestore + Cloud Storage

The app code is backend-agnostic: it reads env vars to pick its storage. With the vars below set,
it uses Firestore (cases) and GCS (media); with none set, it stays on local SQLite + local files
(dev/test). On Cloud Run the Google client libraries authenticate via the service account
(Application Default Credentials) — no DB/storage keys needed.

## Environment variables the app reads
| Var | Purpose | Notes |
|---|---|---|
| `USE_FIRESTORE=1` | Use Firestore for cases | else SQLite/D1 |
| `FIRESTORE_PROJECT` | GCP project for Firestore | optional; inferred from ADC on Cloud Run |
| `FIRESTORE_COLLECTION` | Collection name | optional, default `cases` |
| `GCS_BUCKET` | Bucket for media | presence switches media to GCS |
| `GCS_PROJECT` | GCP project for GCS | optional; inferred from ADC |
| `GOOGLE_API_KEY` | Gemini API key | the only secret; or use Vertex AI (see below) |
| `PORT` | Listen port | set automatically by Cloud Run |

## One-time setup (your machine)
```bash
# 1. Install gcloud, then:
gcloud auth login
gcloud config set project <PROJECT_ID>

# 2. Enable APIs
gcloud services enable run.googleapis.com firestore.googleapis.com \
  storage.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com generativelanguage.googleapis.com

# 3. Create Firestore (Native mode) — ONE per project, region is permanent
gcloud firestore databases create --location=nam5         # or e.g. us-central1

# 4. Create the media bucket (keep region same as Cloud Run; US regions for the free tier)
gcloud storage buckets create gs://<BUCKET> --location=us-central1 --uniform-bucket-level-access

# 5. Store the Gemini key as a secret
printf '%s' '<YOUR_GEMINI_API_KEY>' | gcloud secrets create gemini-key --data-file=-
```

## Deploy
```bash
gcloud run deploy home-rescue \
  --source . \                         # Cloud Build builds the Dockerfile (no local Docker needed)
  --region us-central1 \
  --allow-unauthenticated \            # app uses its own per-device X-User-Id, no login
  --set-env-vars USE_FIRESTORE=1,GCS_BUCKET=<BUCKET>,FIRESTORE_PROJECT=<PROJECT_ID> \
  --set-secrets GOOGLE_API_KEY=gemini-key:latest
```

### IAM (the runtime service account needs DB + bucket access)
Cloud Run runs as a service account (the Compute Engine default SA unless you set one). Grant it:
```bash
# Replace SA with your Cloud Run runtime service account email.
gcloud projects add-iam-policy-binding <PROJECT_ID> \
  --member="serviceAccount:<SA>" --role="roles/datastore.user"
gcloud storage buckets add-iam-policy-binding gs://<BUCKET> \
  --member="serviceAccount:<SA>" --role="roles/storage.objectAdmin"
# And let it read the secret:
gcloud secrets add-iam-policy-binding gemini-key \
  --member="serviceAccount:<SA>" --role="roles/secretmanager.secretAccessor"
```

## After deploy
1. `gcloud run services describe home-rescue --region us-central1 --format='value(status.url)'`
   -> your backend URL, e.g. `https://home-rescue-xxxx-uc.a.run.app`.
2. Point the Flutter app at it (build time):
   `flutter run -d chrome --dart-define=API_BASE_URL=<URL>` (or `flutter build web/apk/ipa ...`).
3. Verify: open `<URL>/openapi.json`; create an issue and confirm a doc appears in the Firestore
   console; upload a photo and confirm an object appears in the bucket.

## Optional: zero secrets (Vertex AI instead of a Gemini API key)
The agent already supports Vertex via `GOOGLE_GENAI_USE_VERTEXAI`. Enable the Vertex AI API and set
`--set-env-vars GOOGLE_GENAI_USE_VERTEXAI=1,GOOGLE_CLOUD_LOCATION=us-central1` (and drop the
`GOOGLE_API_KEY` secret). Then the app authenticates everything — DB, storage, and Gemini — via the
Cloud Run service account, with no stored secrets at all.

## Free-tier notes
- Firestore Native: ~1 GiB + 50K reads / 20K writes / 20K deletes per day (1 free DB per project).
- GCS Always Free: 5 GB + 1 GB egress/month, US-WEST1/CENTRAL1/EAST1 only — keep the bucket there.
- Cloud Run: generous free request/CPU allowance; scales to zero (first request after idle is slow).
