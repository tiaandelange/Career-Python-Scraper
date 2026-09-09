# GitHub Secrets

Configure these on the GitHub repository (Settings → Secrets and variables → Actions). Never put values in workflow YAML.

## Required for scraping + persistence

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

## Required for the 08:00 digest

- `SMTP_HOST` (e.g. `smtp.gmail.com`)
- `SMTP_PORT` (`587`)
- `SMTP_USERNAME`
- `SMTP_PASSWORD` (app password, not the account password)
- `SMTP_FROM`
- `SMTP_TO`

## Optional official APIs

- `USAJOBS_API_KEY`
- `USAJOBS_USER_AGENT`
- `ADZUNA_APP_ID`
- `ADZUNA_APP_KEY`

USAJOBS and Adzuna adapters stay disabled in `config/sources.yaml` until you enable them **and** set the secrets.
