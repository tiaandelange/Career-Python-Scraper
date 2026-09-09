# Source audit

Preference order used throughout: official public API → official RSS → public ATS JSON → employer career API → permitted static HTML → browser automation last. LinkedIn and Indeed are not dependencies. Sources that require CAPTCHA, login, or anti-bot bypass were not implemented.

## Enabled — initial set

### RemoteOK
- **URL/domain:** remoteok.com
- **Region:** Global
- **Coverage:** Remote
- **Access:** Official public JSON `GET https://remoteok.com/api`
- **Auth:** No
- **Free:** Yes
- **Salary:** Often present (`salary_min` / `salary_max`)
- **Pagination:** Single dump
- **Rate limit:** Be polite; one call per scrape
- **robots/automation:** Public API intended for reuse
- **JavaScript:** No
- **Stability:** High
- **Adapter:** `job_scout.adapters.remote.remoteok.RemoteOKAdapter`
- **Enabled:** Yes
- **Reason:** First-party JSON, salary fields, no key.

### Remotive
- **URL/domain:** remotive.com
- **Region:** Global
- **Coverage:** Remote
- **Access:** Official public API `GET https://remotive.com/api/remote-jobs`
- **Auth:** No
- **Free:** Yes
- **Salary:** Sometimes a text field
- **Pagination:** Search/limit
- **Rate limit:** Unknown; keyword-limited queries
- **JavaScript:** No
- **Stability:** High
- **Adapter:** `job_scout.adapters.remote.remotive.RemotiveAdapter`
- **Enabled:** Yes
- **Reason:** Official API, good remote coverage including PM/ops.

### Jobicy
- **URL/domain:** jobicy.com
- **Region:** Global (geo filter available)
- **Coverage:** Remote
- **Access:** Official API `GET https://jobicy.com/api/v2/remote-jobs`
- **Auth:** No
- **Free:** Yes
- **Salary:** Often
- **Pagination:** `count` max 100
- **JavaScript:** No
- **Stability:** High
- **Adapter:** `job_scout.adapters.remote.jobicy.JobicyAdapter`
- **Enabled:** Yes
- **Reason:** Documented public API, no key.

### Himalayas
- **URL/domain:** himalayas.app
- **Region:** Global
- **Coverage:** Remote
- **Access:** Official API `GET https://himalayas.app/jobs/api/search`
- **Auth:** No
- **Free:** Yes
- **Salary:** Structured min/max + period + currency
- **Pagination:** `page` / cursor; 20 per page; data cached ~24h
- **Rate limit:** 429 if abused
- **JavaScript:** No
- **Stability:** High
- **Adapter:** `job_scout.adapters.remote.himalayas.HimalayasAdapter`
- **Enabled:** Yes
- **Reason:** Explicit `locationRestrictions` and `timezoneRestrictions` — required for remote eligibility.

### We Work Remotely
- **URL/domain:** weworkremotely.com
- **Region:** Global
- **Coverage:** Remote
- **Access:** Official category RSS
- **Auth:** No
- **Free:** Yes
- **Salary:** Rare
- **Pagination:** Feed window
- **JavaScript:** No
- **Stability:** High
- **Adapter:** `job_scout.adapters.remote.weworkremotely.WeWorkRemotelyAdapter`
- **Enabled:** Yes
- **Reason:** RSS, no HTML scraping.

### Greenhouse / Lever / Ashby / SmartRecruiters / Workable
- **URL/domain:** boards-api.greenhouse.io, api.lever.co, api.ashbyhq.com, api.smartrecruiters.com, apply.workable.com
- **Region:** Configured employers (ZA / US / EU / AU as posted)
- **Coverage:** Remote, hybrid, on-site (as labelled by the employer)
- **Access:** Public ATS job-board JSON (the same endpoints career widgets use)
- **Auth:** No
- **Free:** Yes
- **Salary:** Unreliable except Ashby when compensation is opted in
- **Pagination:** Greenhouse/Lever/Ashby usually one shot; SmartRecruiters offset
- **JavaScript:** No
- **Stability:** High for Greenhouse/Lever/Ashby; Workable widget is public but less formally documented
- **Adapters:** `adapters/ats/*.py` — one adapter, many employer slugs in `config/sources.yaml`
- **Enabled:** Yes (empty employer lists until you add verified board slugs)
- **Reason:** Reusable, legal, no per-company scraper. Guessed engineering-firm slugs (Stantec, Arup, Hatch, etc.) returned 404 on a live check, so they were removed rather than left to waste GitHub Actions minutes. Add a slug only after `curl` against the public board URL returns 200.

### EURES
- **URL/domain:** europa.eu/eures
- **Region:** EU / EEA
- **Coverage:** Mostly on-site / hybrid
- **Access:** Public JSON search
- **Auth:** No
- **Free:** Yes
- **Salary:** Sometimes
- **Pagination:** `page` / `resultsPerPage`
- **JavaScript:** No
- **Stability:** Medium (public search engine; schema may evolve)
- **Adapter:** `job_scout.adapters.regional.eures.EuresAdapter`
- **Enabled:** Yes
- **Reason:** Official EU portal. Keyword-capped to stay inside GitHub Actions time.

### Arbeitnow
- **URL/domain:** arbeitnow.com
- **Region:** Europe
- **Coverage:** Remote + on-site
- **Access:** Public JSON `GET https://www.arbeitnow.com/api/job-board-api`
- **Auth:** No
- **Free:** Yes
- **Salary:** Rare
- **Pagination:** Single payload
- **JavaScript:** No
- **Stability:** Medium-high
- **Adapter:** `job_scout.adapters.regional.arbeitnow.ArbeitnowAdapter`
- **Enabled:** Yes
- **Reason:** Public API covering European engineering/ops listings.

## Disabled pending credentials (implemented)

### USAJOBS
- Official API at data.usajobs.gov. Free key via developer.usajobs.gov. Salary usually published. Many roles require US citizenship — flagged, not assumed. **Enabled: no** until `USAJOBS_API_KEY`.

### Adzuna
- Official developer API with salary fields for ZA, US, AU and several EU countries. **Enabled: no** until `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. Free developer tier; still an aggregator, so ranked below ATS/employer sources.

## Deliberately excluded

| Source | Reason |
| --- | --- |
| LinkedIn | ToS / anti-bot. Not a dependency. |
| Indeed | ToS / anti-bot. Not a dependency. |
| PNet / CareerJunction | No official public API; JS-heavy HTML. |
| SEEK | No official public API; scraping prohibited. |
| Glassdoor | Anti-bot; salary *estimates* are forbidden as published pay. |
| DPSA vacancy circular | Weekly PDF, not a job API. |
| APS Jobs | Salesforce/JS; would need Playwright. |
| Workday career sites | Undocumented POST endpoints; not treated as official public APIs. |
| Paid job APIs / proxies / CAPTCHA solvers | Out of free-tier policy. |

## South Africa note

There is no high-quality free official JSON/RSS board for private-sector mechanical/infrastructure jobs in South Africa that meets the access rules. Coverage for ZA on-site/hybrid therefore depends on (1) employer ATS boards you add as slugs, and (2) optional Adzuna once a free key exists. This is an honest limitation, not a missing scraper.
