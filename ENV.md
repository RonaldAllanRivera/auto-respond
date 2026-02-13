# Environment Variables

This document defines the environment variable contract for local development and Render deployment.

## Local development (Docker Compose)

Copy `.env.example` to `.env` and set values.

Required for running the backend locally:

- `DJANGO_SECRET_KEY`

Recommended (required once AI answering is enabled):

- `OPENAI_API_KEY`

Recommended for local dev:

- `DJANGO_DEBUG=1`
- `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`

Recommended for device pairing:

- `DEVICE_TOKEN_SECRET`

## Static files

Static assets are served via WhiteNoise in the container. No additional environment variables are required.

Database variables (Docker Compose defaults are provided):

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Production (Render)

Recommended settings:

- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=<your-service>.onrender.com`

You should also configure database variables from Render Postgres.

## OpenAI

- `OPENAI_API_KEY`: required
- `OPENAI_MODEL`: default `gpt-4o-mini`
- `OPENAI_TIMEOUT_SECONDS`: default `15`

## SaaS roadmap variables (used in later phases)

### Google OAuth

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

Notes:

- See README.md for required redirect URI(s) and the Django Sites domain configuration for allauth.

### Stripe

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

Pricing notes:

- This project will support a **Monthly subscription** in Stripe.
- The Stripe **Price ID** for that plan is configured via the Django Admin Billing Plan CMS (stored in the database), not via environment variables.

## Current scaffold security variables

The scaffold uses **device pairing + server-issued device tokens** for extension-to-backend requests.

- `DEVICE_TOKEN_SECRET`
