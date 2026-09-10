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

### ReliefWeb
- **URL/domain:** reliefweb.int
- **Region:** Global (humanitarian / development)
- **Coverage:** Mostly on-site / hybrid field roles; some remote
- **Access:** Official jobs RSS `GET https://reliefweb.int/jobs/rss.xml` (REST `/v1/jobs` returned HTTP 410 when checked)
- **Auth:** No
- **Free:** Yes
- **Salary:** Rare
- **Pagination:** Feed window (~20)
- **JavaScript:** No
- **Stability:** High for RSS
- **Adapter:** `job_scout.adapters.regional.reliefweb.ReliefWebAdapter`
- **Enabled:** Yes
- **Reason:** Strong WASH / infrastructure / expat niche analogue to TeachAway-style specialty boards.

### DPSA Public Service Vacancy Circular (ZA)
- **URL/domain:** dpsa.gov.za/newsroom/psvc
- **Region:** South Africa (national + provincial administrations)
- **Coverage:** On-site / hybrid public-service posts (Chief Engineer, Civil/Mechanical, etc.)
- **Access:** Weekly circular HTML index → section PDFs (e.g. Limpopo `.../2026/32/s.pdf`) parsed with `pypdf`
- **Auth:** No
- **Free:** Yes
- **Salary:** Usually published as **annual ZAR** (OSD grades A–C common)
- **Pagination:** Latest N circulars (default 2); engineering keyword filter before ingest
- **JavaScript:** No
- **Stability:** Medium (PDF layout quirks); URL pattern is stable week-to-week
- **Adapter:** `job_scout.adapters.regional.dpsa_circular.DpsaCircularAdapter`
- **Enabled:** Yes
- **Reason:** Primary weekly channel for national and provincial public-service engineering posts (OSD salaries).

### DWS Vacancies (ZA HTML bulletins)
- **URL/domain:** https://www.dws.gov.za/vacancies/default.aspx → `current/{date}.aspx`
- **Region:** South Africa (Department of Water and Sanitation)
- **Coverage:** On-site engineering / technologist / water-resource posts
- **Access:** HTML bulletin tables with per-post PDFs; apply via https://erecruitment.dws.gov.za
- **Auth:** No
- **Free:** Yes
- **Salary:** Usually published annual ZAR OSD packages in the PDF
- **Pagination:** Latest N bulletins (default 3)
- **JavaScript:** No
- **Adapter:** `job_scout.adapters.regional.dws_vacancies.DwsVacanciesAdapter`
- **Enabled:** Yes
- **Reason:** Direct DWS feed updated regularly; earlier audit incorrectly assumed the ASPX pages were unusable.

### DPWI Vacancies (ZA PDF index)
- **URL/domain:** http://www.publicworks.gov.za/vacancies.html
- **Region:** South Africa (Public Works & Infrastructure)
- **Coverage:** Mechanical / civil / construction project management
- **Access:** HTML index of DPSA-format PDF adverts
- **Adapter:** `job_scout.adapters.regional.dpwi_vacancies.DpwiVacanciesAdapter`
- **Enabled:** Yes

### SA PDF boards (water boards)
- **Boards:** Magalies Water, Lepelle Northern Water, Overberg Water
- **Access:** HTML indexes linking vacancy PDFs
- **Adapter:** `job_scout.adapters.regional.sa_pdf_boards.SaPdfBoardAdapter`
- **Enabled:** Yes

### Next candidates (researched, not yet enabled)
- Western Cape / Gauteng e-recruit portals — need session or search-form handling
- City of Johannesburg SharePoint vacancies — thin index today
- SANRAL careers table — JS-rendered (adapter stub exists, disabled)
- Rand Water / Eskom — login or portal-down
- Provincial OTP e-recruit (Limpopo, EC, Mpumalanga) — ASP.NET ViewState / login friction

Provincial engineering posts remain largely covered via **DPSA circular section PDFs**.

### Remote1stJobs
- **URL/domain:** remote1stjobs.com
- **Region:** Global / EMEA-leaning remote
- **Coverage:** Remote
- **Access:** Public JSON `GET https://www.remote1stjobs.com/jobs.json`
- **Auth:** No
- **Free:** Yes
- **Salary:** Rare in feed
- **Pagination:** Single dump (capped by `max_jobs_per_source`)
- **JavaScript:** No
- **Stability:** Medium
- **Adapter:** `job_scout.adapters.remote.remote1stjobs.Remote1stJobsAdapter`
- **Enabled:** Yes
- **Reason:** Extra remote inventory; family filter keeps mechanical/infra hits.

### Greenhouse / Lever / SmartRecruiters employers (verified water/infra)
- Greenhouse: `mackaysposito`, `bgeinc`
- Lever: `woodardcurran`, `stanleygroup`
- SmartRecruiters: `AECOM2`, `Ingerop`, `Ramboll3`
- **Enabled:** Yes (page-capped on SmartRecruiters)
- **Reason:** Live dams / pipelines / water consulting boards confirmed via public ATS JSON. WSP Africa API slug returned empty and was not added. Workday (SMEC) stays excluded.

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
| Facebook / Meta jobs | Login / anti-bot; no free personal jobs API. |
| TeachAway | Teacher niche; no public jobs API/RSS for this profile. |
| Devex / Rigzone / Careermine | No free public jobs retrieval (or bot-check HTML). |
| UN Careers “jobfeed” | Returns SPA HTML, not RSS. |
| PNet / CareerJunction | No official public API; JS-heavy HTML. |
| SEEK | No official public API; scraping prohibited. |
| Glassdoor | Anti-bot; salary *estimates* are forbidden as published pay. |
| DPSA vacancy circular | **Now enabled** — weekly section PDFs parsed (was previously excluded as “PDF only”). |
| Government Gazette | Not used as vacancy feed; engineer posts come via DPSA circular. |
| limpopo.gov / dws.gov careers HTML | Not usable feeds; vacancies route through DPSA. |
| APS Jobs | Salesforce/JS; would need Playwright. |
| Workday career sites | Undocumented POST endpoints; not treated as official public APIs. |
| Paid job APIs / proxies / CAPTCHA solvers | Out of free-tier policy. |

## South Africa note

ZA public-service engineering posts (including provincial Engineering Services and posts that appear under Water & Sanitation when advertised) are ingested from **DPSA weekly circular PDFs**. Private-sector ZA coverage still relies mainly on SmartRecruiters boards (AECOM, Ingérop) plus optional Adzuna keys. Direct scraping of `limpopo.gov.za` / broken `dws.gov.za` careers HTML is not used.
