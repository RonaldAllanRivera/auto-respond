# Environment Variables

This document defines the environment variable contract for local development and Render deployment.

## Local development (Docker Compose)

Copy `.env.example` to `.env` and set values.

Required for running the backend locally:

- `DJANGO_SECRET_KEY`
- `OPENAI_API_KEY`

Recommended for local dev:

- `DJANGO_DEBUG=1`
- `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`

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

### Stripe

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

Pricing notes:

- This project will support a **Monthly subscription** in Stripe.
- The Stripe **Price ID** for that plan is configured via the Django Admin Billing Plan CMS (stored in the database), not via environment variables.

## Current scaffold security variables

The current scaffold uses a shared-key + token approach for extension-to-backend requests:

- `EXTENSION_BOOTSTRAP_KEY`
- `EXTENSION_TOKEN_SECRET`

In the SaaS phases, this will be replaced by extension device pairing and server-issued device tokens.
