# Cloud Run deployment

## Required Google Cloud setup

1. Select a Google Cloud project with billing enabled.
2. Enable Cloud Run, Cloud Build, Artifact Registry, Secret Manager, and Maps Static API.
3. Create the two secrets without putting their values in source control:

```powershell
gcloud secrets create GEMINI_API_KEY --replication-policy=automatic
gcloud secrets versions add GEMINI_API_KEY --data-file=<path-to-a-local-key-file>
gcloud secrets create GOOGLE_MAPS_API_KEY --replication-policy=automatic
gcloud secrets versions add GOOGLE_MAPS_API_KEY --data-file=<path-to-a-local-key-file>
```

4. Grant the Cloud Run service account Secret Manager Secret Accessor for both secrets.

## Build and deploy

Run from the repository root after replacing the placeholders:

```powershell
gcloud builds submit backend --tag REGION-docker.pkg.dev/PROJECT_ID/REPOSITORY/traffic-backend:latest
gcloud run deploy traffic-backend `
  --image REGION-docker.pkg.dev/PROJECT_ID/REPOSITORY/traffic-backend:latest `
  --region REGION `
  --allow-unauthenticated `
  --set-secrets GEMINI_API_KEY=GEMINI_API_KEY:latest,GOOGLE_MAPS_API_KEY=GOOGLE_MAPS_API_KEY:latest `
  --set-env-vars GEMINI_VISION_MODEL=gemini-3.5-flash,GEMINI_REASONING_MODEL=gemini-3.5-flash,GEMINI_IMAGE_MODEL=gemini-3.1-flash-image `
  --memory 2Gi `
  --cpu 2 `
  --timeout 300 `
  --concurrency 4
```

Set `CORS_ORIGINS` to the deployed frontend origin before production use. The evaluation prompt and
classic cases are copied into the container by the Dockerfile. Updating either requires a new image.
