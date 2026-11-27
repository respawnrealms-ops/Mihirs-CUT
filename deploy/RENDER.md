# Mihis Cut on Render

Use a Docker **Web Service** with one instance and a persistent disk mounted at `/data`.
The same process serves the website and runs recording, rendering and scheduled posting.
Do not create a second worker against the same files or enable multiple instances.

## Cost and capacity

`render.yaml` selects **2 CPU / 8 GB RAM** (`2c-8g`) and a **50 GB persistent disk**.
At the prices checked on 27 November 2026 this is approximately **$147.50/month**
($135 compute + $12.50 disk), before tax, bandwidth overages, and AI-provider usage.
Check the actual estimate in Render before applying the Blueprint. This is not a free deployment.

Only one video is processed at a time and one live stream can record at a time. Rendering is
slower than on a powerful desktop. Free/512 MB instances cannot reliably run the speech model,
and Render Free sleeps and does not support persistent disks.

Sources: https://render.com/pricing and https://render.com/docs/free

## Deploy

1. Sign in at https://dashboard.render.com and connect the `respawnrealms-ops/Mihirs-CUT` repository.
2. Choose **New → Blueprint**, select the branch containing this file and `render.yaml`,
   and review the service and disk cost. Apply only when you accept the displayed charges.
3. Render builds the existing Dockerfile. No separate build or start command is needed.
   `deploy/render_start.py` sets the public URL from `RENDER_EXTERNAL_URL` and listens on `PORT`.
4. Open the generated HTTPS `onrender.com` address. Sign-in is enabled. Create your account,
   then in the Render Shell run `python -m studio.admin grant YOUR_EMAIL` to make it an admin.
5. Add your AI settings in the app. For sharing with others, configure SMTP and
   `PEAKCUT_VERIFY_EMAIL=1`; otherwise email verification and password-reset delivery are unavailable.
   Each user can save their own AI settings. A global AI key would be available for all users' work.
6. Under Settings → Connected apps, configure YouTube with the new redirect URL:
   `https://YOUR_RENDER_HOST/oauth/youtube/callback`. Add that exact URL to your Google OAuth
   client's authorized redirects. For Google app sign-in also add `/auth/google/callback`.
   Reconnect YouTube from the hosted app before uploading there.
7. Test an owned YouTube link, a small uploaded file, and a private YouTube upload.
   YouTube may refuse downloads from data-center IPs. The app has cookie settings to help,
   but downloading successfully from a desktop does not guarantee the same on a cloud host.

There is no custom domain requirement. A custom domain can be added later; set
`PEAKCUT_PUBLIC_URL` and update the platform callback URLs if the address changes.

## Storage, existing data and updates

The initial deployment is a new installation. Local `.env`, tokens, browser cookies, videos,
and databases are excluded from the Docker build. Existing desktop data is not uploaded automatically.
Moving it needs a separate migration: local jobs contain Windows file paths, and the desktop's
built-in owner must be assigned to a hosted sign-in account. Do not copy the desktop data blindly.

SQLite, connected accounts, videos, speech models and posting state live under the persistent `/data`
disk. Do not remove the disk when updating. Use Render disk snapshots/backups and keep separate backups
of important source material. The configured 35 GB per-user limit leaves space for models and temporary
files on the 50 GB disk; increase storage if using long recordings or several people.

Automatic deploys are off to avoid unexpectedly interrupting a recording. Stop live capture and wait
for active work to finish before a manual deploy. Render can still restart services for maintenance.
The existing app recovers queued jobs and posting state after a restart.

For ordinary manual setup instead of a Blueprint, select Docker, set the start command to
`python deploy/render_start.py`, copy the environment settings from `render.yaml`, mount `/data`,
set health check `/healthz`, and keep exactly one instance.
