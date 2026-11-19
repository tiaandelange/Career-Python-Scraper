# Analyst Scout — Fork & Build Guide
### Hoe om hierdie dokument met Claude te gebruik
> **Afrikaans kort nota vir jou vriend:**
> Plak die _hele_ inhoud van hierdie lêer (van kop tot by die checklist) as jou eerste boodskap aan Claude.
> Sê dan net: _"Ek wil 'n nuwe Python scraper bou vir afstandsanalis-poste. Gebruik hierdie gids as my konteks en help my stap vir stap."_
> Claude sal die argitektuur van Job Scout verstaan en jou deur elke stap lei sonder dat jy iets moet verduidelik.
> Onthou: voer die produkbriefing in §A volledig in voordat jy begin bou — dit bepaal elke YAML-waarde en elkeen van die scoring-reëls.

---

## A. Product Brief — Vul Dit In Eers

> **Instruksie:** Kopieer hierdie blok na 'n nuwe `config/brief.md` in jou fork. Vul elke `TODO` in. Wanneer jy 'n bou-stap bereik waar 'n YAML-lêer verander moet word, plak jou voltooide brief as konteks saam met die vraag aan Claude.

```markdown
### My Analyst Scout — Product Brief

**Candidate summary (1–2 sentences):**
TODO  # e.g. "Mid-senior analyst at a South African hedge fund (PAMRS). Quant-adjacent
       #  background; curious about fintech, research, and operations."

**Primary job families (rank-order, most wanted first):**
TODO  # e.g. financial analyst, business analyst, data analyst,
       #  research analyst, operations analyst, strategy analyst

**Title keywords to INCLUDE (exact strings the scraper must match):**
TODO  # e.g. analyst, quant analyst, investment analyst, research analyst,
       #  business intelligence, data analyst, ops analyst

**Title keywords to EXCLUDE (too far off-niche):**
TODO  # e.g. software engineer, nurse, teacher, accountant, driver,
       #  marketing coordinator (unless "marketing analytics")

**Work mode (check all that apply):**
- [ ] Remote worldwide  ← primary target
- [ ] Remote with timezone window (UTC±3 acceptable)
- [ ] Part-time / fractional  ← also welcome
- [ ] Hybrid (only if country below)  ← secondary
- [ ] Onsite — NOT in scope for this scout

**Geography for onsite/hybrid (leave blank if remote-only):**
TODO  # e.g. South Africa only, or leave blank

**Hours / week preference:**
TODO  # e.g. "10–25 h/week part-time preferred; full-time roles also surfaced"
       #  This drives the part-time detection rule in §D.

**Salary floors (monthly, employer-published only):**
- ZAR (remote ZA): TODO   # e.g. 25000
- USD (remote global): TODO  # e.g. 1500  (part-time; scale to ~3000+ for full-time)
- EUR (remote EU): TODO   # e.g. 1400

**Part-time / hourly floor (if different from above):**
TODO  # e.g. USD 25/hr minimum if hourly rate published

**Remote geo rules:**
TODO  # e.g. "Accept worldwide, global, EMEA, Africa, UTC±3.
       #  Flag but keep if scope is unknown.
       #  Reject if advert explicitly excludes Africa."

**Sectors you find interesting (boosts score, not hard filter):**
TODO  # e.g. fintech, hedge funds, private equity, investment management,
       #  asset management, venture capital, research consultancies,
       #  development finance, central banking, insurance/actuarial

**Skills you actually have (honest list — drives skills_positive in scoring.yaml):**
TODO  # e.g. Excel/Google Sheets, SQL, Python (scripting), R,
       #  financial modelling, Bloomberg terminal, PowerBI/Tableau,
       #  report writing, presentation, stakeholder management, VBA

**Tools / certifications to highlight:**
TODO  # e.g. CFA candidate, Bloomberg certified, Power BI, dbt, etc.

**Seniority range:**
TODO  # e.g. "Mid (3–7 years) up to senior; avoid C-suite or graduate"

**Existing work rights / visa:**
- South Africa: YES (citizen / permanent)
- USA: NO — sponsorship required or remote OK
- EU: NO — remote only or sponsorship
```

---

## B. Ordered Build Steps

### 1 · Fork / Clone

```bash
# On GitHub: fork https://github.com/<your-org>/Career-Python-Scraper
# Then locally:
git clone https://github.com/<you>/analyst-scout.git
cd analyst-scout
git remote add upstream https://github.com/<original-org>/Career-Python-Scraper.git

# Create a clean Python 3.12 environment
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -e .
```

**Rename the package immediately** so it doesn't collide with Job Scout if both run on the same machine:

```bash
# In pyproject.toml change:  name = "job-scout"  →  name = "analyst-scout"
# In pyproject.toml change:  [project.scripts]
#                             job_scout = "job_scout.__main__:main"
#                         →   analyst_scout = "job_scout.__main__:main"
# (You can rename the src/job_scout/ directory to src/analyst_scout/ later,
#  but it is not required before first run.)
```

---

### 2 · Rewrite `config/profile.yaml`

Replace the entire file with an analyst profile. Below is a **template** — fill every `TODO` from your §A brief before saving.

```yaml
candidate:
  name: "Remote / Part-time Analyst"
  summary: >
    TODO  # Paste your candidate summary from the brief.
  qualifications:
    - TODO  # e.g. "BCom Finance" or "BSc Statistics"
    - TODO  # e.g. "CFA Level 2 candidate"
  do_not_claim:
    - senior software engineer
    - machine learning researcher
    - data scientist (pure ML/research)
    - US / EU work rights unless role is fully remote

primary_capabilities:
  # Paste your "Skills you actually have" list here, one item per line
  - TODO  # e.g. financial modelling
  - TODO  # e.g. SQL
  - TODO  # e.g. Excel
  - TODO  # e.g. Python scripting
  - TODO  # e.g. report writing

digital_transferable:
  note: >
    Proficiency with standard analyst tooling: spreadsheets, SQL, BI dashboards,
    scripting. Not a career software engineer.
  skills:
    - Excel
    - Google Sheets
    - SQL
    - Python scripting
    - Power BI
    - Tableau
    - Bloomberg
    - R
    - dbt
    - Jupyter notebooks
  not_equivalent_to:
    - senior software engineer
    - data engineer (platform)
    - ML engineer
    - backend engineer

job_families:
  financial_analyst:
    weight: 1.0
    titles:
      - Financial Analyst
      - Senior Financial Analyst
      - Investment Analyst
      - Equity Analyst
      - Credit Analyst
      - Quantitative Analyst
      - Quant Analyst
      - Portfolio Analyst
      - Fund Analyst
      - Research Analyst
      - Fixed Income Analyst
    keywords:
      - financial analysis
      - investment research
      - equity research
      - portfolio management
      - financial modelling
      - valuation
      - Bloomberg
      - CFA
      - quant
  business_analyst:
    weight: 0.9
    titles:
      - Business Analyst
      - Senior Business Analyst
      - Strategy Analyst
      - Commercial Analyst
      - Revenue Analyst
      - Pricing Analyst
      - Planning Analyst
    keywords:
      - business analysis
      - requirements gathering
      - process improvement
      - stakeholder
      - strategic analysis
      - commercial
  data_analyst:
    weight: 0.9
    titles:
      - Data Analyst
      - Senior Data Analyst
      - Analytics Analyst
      - Business Intelligence Analyst
      - BI Analyst
      - Insights Analyst
    keywords:
      - data analysis
      - business intelligence
      - dashboards
      - SQL
      - Power BI
      - Tableau
      - Looker
      - data visualisation
  research_analyst:
    weight: 0.85
    titles:
      - Research Analyst
      - Market Research Analyst
      - Macro Analyst
      - Sector Analyst
      - Policy Analyst
    keywords:
      - research report
      - market research
      - macroeconomic
      - sector analysis
      - policy analysis
      - literature review
  operations_analyst:
    weight: 0.75
    titles:
      - Operations Analyst
      - Ops Analyst
      - Process Analyst
      - Efficiency Analyst
      - Workflow Analyst
    keywords:
      - operations analysis
      - process analysis
      - workflow optimisation
      - operational efficiency

geographic:
  remote:
    origin_anywhere: true
    prefer_scopes:
      - worldwide
      - anywhere
      - global
      - emea
      - africa
      - south_africa
      - timezone_compatible
    reject_if_explicitly_excludes_south_africa: true
    keep_unknown: true
    flag_unknown: true
  onsite_hybrid_countries:
    - ZA    # South Africa only for onsite/hybrid; remove if remote-only
  search_regions:
    - South Africa
    - Worldwide Remote
  assume_work_rights:
    ZA: true
    US: false
    EU: false
    AU: false

hard_filters:
  reject_inactive: true
  reject_expired: true
  reject_empty_title: true
  reject_empty_company_optional: false
  flag_unknown_visa_status: true
  never_invent_salary: true
  never_use_third_party_salary_estimates: true
```

---

### 3 · Rewrite `config/scoring.yaml`

Replace the entire file. Key changes from Job Scout:
- `professional_positive` targets analyst vocabulary instead of engineering.
- `unrelated_roles` now includes mechanical/civil engineering (they are unrelated to analysts).
- `digital_overclaim_penalties` carried over — still protect against pure-SE roles.

```yaml
weights:
  professional_relevance: 30   # highest — must be an analyst role
  skills: 20                   # your actual tool stack
  seniority: 6
  sector: 10                   # fintech / investment preferred
  part_time_fit: 8             # NEW — rewards explicit part-time / fractional signal
  digital_transferability: 5
  compensation: 8
  work_mode: 7                 # all-remote = full points
  international_mobility: 6

categories:
  Exceptional: [88, 100]
  Strong: [75, 87]
  Good: [62, 74]
  Possible: [50, 61]
  Low: [0, 49]

digest_minimum_category: Possible
low_score_cutoff: 50

professional_positive:
  # Analyst vocabulary — replace with your actual target terms from the brief
  - analyst
  - financial analyst
  - investment analyst
  - business analyst
  - data analyst
  - research analyst
  - operations analyst
  - quantitative analyst
  - quant
  - equity research
  - credit analysis
  - financial modelling
  - valuation
  - portfolio
  - financial reporting
  - variance analysis
  - forecasting
  - budgeting
  - KPI
  - dashboard
  - insights
  - due diligence

skills_positive:
  # Your real skills from the brief — honest list only
  - Excel
  - SQL
  - Python
  - R
  - Power BI
  - Tableau
  - Bloomberg
  - financial model
  - DCF
  - scenario analysis
  - pivot table
  - VLOOKUP
  - Google Sheets
  - report writing
  - stakeholder communication
  - Jupyter
  - dbt
  - Looker

seniority_positive:
  - senior
  - lead
  - principal
  - manager
  - head of
  - director

seniority_not_required:
  - mid-level
  - intermediate
  - associate

sectors_high:
  # Sectors you find genuinely interesting
  - fintech
  - hedge fund
  - investment management
  - asset management
  - private equity
  - venture capital
  - investment bank
  - development finance
  - central bank
  - insurance
  - actuarial
  - research consultancy
  - economic research
  - market research
  - management consulting

# Part-time positive signals (feeds part_time_fit weight above)
part_time_positive:
  - part-time
  - part time
  - parttime
  - fractional
  - contract
  - freelance
  - flexible hours
  - 20 hours
  - 15 hours
  - 10 hours
  - hourly
  - per hour
  - /hr
  - /hour
  - remote contractor

leadership_positive:
  - team lead
  - leadership
  - manage
  - mentoring
  - programme
  - delivery

digital_positive:
  - automation
  - workflow
  - AI-assisted
  - business process
  - low-code
  - no-code
  - technical analyst
  - product analyst

digital_overclaim_penalties:
  - senior software engineer
  - staff software engineer
  - principal software engineer
  - java architect
  - .net architect
  - embedded firmware
  - compiler
  - distributed systems architect
  - machine learning engineer
  - kubernetes platform
  - sre
  - backend engineer
  - frontend engineer
  - full stack engineer

unrelated_roles:
  # Everything that is clearly not analyst work
  - mechanical engineer
  - civil engineer
  - structural engineer
  - water engineer
  - site inspector
  - electrician
  - plumber
  - surgeon
  - physician
  - nurse
  - teacher
  - chef
  - truck driver
  - police
  - pharmacist
  - dentist
  - marketing coordinator   # remove if you want marketing analytics
  - sales representative
  - recruiter

work_mode_boost:
  remote_global: 7
  remote_unknown: 2
  hybrid: 1
  onsite: 0

mobility_boost:
  visa_sponsorship: 6
  relocation: 3
  globally_distributed: 4

mobility_penalty:
  citizenship_required: 20
  unrestricted_work_rights: 15
  missing_licence: 5

compensation:
  bonus_start_multiple_of_floor: 1.1
  max_bonus_points: 8
```

> **Note on `part_time_fit`:** The built-in `score_job()` function in
> `src/job_scout/services/scoring.py` does not yet have a `part_time_fit`
> dimension. After adding `part_time_positive` to `scoring.yaml`, add ~10 lines
> to `score_job()` that call `_hits(blob, scoring.get("part_time_positive") or [])`
> and assign the result to `breakdown.operations_alt` (reuse the spare bucket)
> or add a new `PartTimeFit` field to `ScoreBreakdown`. See §D for the
> exact detection rule.

---

### 4 · Rewrite `config/salary_policy.yaml`

Adjust floors to match your brief. Example for a part-time-friendly analyst scout:

```yaml
# Employer-published salary only. Never invent figures.
currency_floors_monthly:
  ZAR: 25000     # TODO — your ZAR floor from the brief
  USD: 1500      # TODO — your USD floor (part-time; raise for full-time)
  EUR: 1400      # TODO — your EUR floor

# Part-time / hourly floor (do NOT annualise hourly rates at 40 h/week — see §D)
part_time_hourly:
  usd_per_hour_floor: 20   # TODO — your hourly floor from the brief
  do_not_assume_hours_per_week: true  # flag only; normalisation note below

default_international_floor:
  currency: USD
  amount_monthly: 1500     # TODO — same as USD above

no_maximum: true

rules:
  onsite_requires_published_salary: false   # part-time remote often unpublished
  hybrid_requires_published_salary: false
  remote_allows_missing_salary: true
  reject_known_salary_below_floor: true
  range_uses_lower_bound: true
  never_invent_missing_salary: true
  never_infer_from_glassdoor_or_estimates: true
  store_published_separately_from_estimates: true

fx:
  provider: frankfurter
  api_url: https://api.frankfurter.dev/v1/latest
  cache_daily: true
  fallback_to_stale_cache: true
  never_fabricate_rate: true

normalisation:
  annual_divisor: 12
  weekly_multiplier: 4.3333333333
  daily_days_per_week: 5
  # Part-time rule: if an advert shows an hourly rate, DO NOT multiply by 40.
  # Store the raw hourly figure; compare against part_time_hourly.usd_per_hour_floor.
  # The default 40 h/week assumption (hourly_hours_per_week: 40) is intentionally
  # NOT set here. See §D for the code change needed in salary.py.
  weeks_per_year: 52
```

---

### 5 · Disable Irrelevant Adapters in `config/sources.yaml`

The Job Scout sources below are **South Africa–specific government / infrastructure** boards that produce zero analyst hits. Set `enabled: false` for all of them:

```yaml
  # ── DISABLE THESE ──────────────────────────────────────────────
  dpsa_circular:
    enabled: false   # SA public-service engineering circulars
  dws_vacancies:
    enabled: false   # Dept of Water & Sanitation
  dpwi_vacancies:
    enabled: false   # Dept of Public Works
  sanral_vacancies:
    enabled: false   # SANRAL road-authority careers
  sa_pdf_boards:
    enabled: false   # Water-board PDF vacancy indexes
  reliefweb:
    enabled: false   # Humanitarian / WASH sector
  eures:
    enabled: false   # EU onsite jobs (engineer-heavy)
  arbeitnow:
    enabled: false   # EU onsite jobs
  usajobs:
    enabled: false   # US federal government (citizenship usually required)

  # ── KEEP BUT UPDATE employer slugs ─────────────────────────────
  greenhouse:
    enabled: true
    employers: []    # Replace with analyst-friendly slugs — see §C below
  lever:
    enabled: true
    employers: []    # Replace with analyst-friendly slugs — see §C below
  ashby:
    enabled: true
    employers: []    # Ashby is popular with fintech/research startups — see §C
  smartrecruiters:
    enabled: false   # Job Scout uses it for large engineering firms; disable until
                     # you confirm analyst-hiring companies on SmartRecruiters
  workable:
    enabled: false   # Enable once you find analyst employer slugs on workable.com

  # ── KEEP AS-IS (already remote-analyst-relevant) ───────────────
  remoteok:
    enabled: true
  remotive:
    enabled: true
  jobicy:
    enabled: true
  himalayas:
    enabled: true
  weworkremotely:
    enabled: true
  remote1stjobs:
    enabled: true
```

---

### 6 · Update Remotive Search Queries

Open `src/job_scout/adapters/remote/remotive.py` and replace the `SEARCHES` tuple (line 14–20 in Job Scout) with analyst-relevant queries:

```python
SEARCHES = (
    "financial analyst",
    "business analyst",
    "data analyst",
    "research analyst",
    "operations analyst",
    "quantitative analyst",
    "investment analyst",
    "strategy analyst",
    "part-time analyst",
    "fractional analyst",
)
```

Do the same for **RemoteOK** (`src/job_scout/adapters/remote/remoteok.py`) — check what query/tag parameter that adapter uses and swap engineering tags for `analyst`, `finance`, `data`.

---

### C. Suggested Sources for Remote Analyst

All sources below have **official public APIs or RSS**. No scraping, no login.

| Source | Type | Free | Key? | Best for |
|---|---|---|---|---|
| **Remotive** | JSON API | ✅ | No | Broad remote; filter by `search=` param |
| **RemoteOK** | JSON dump | ✅ | No | Tech-adjacent analyst/finance tags |
| **Jobicy** | JSON API | ✅ | No | Finance/analyst category |
| **Himalayas** | JSON API | ✅ | No | Good salary data; timezone filter |
| **We Work Remotely** | RSS | ✅ | No | Business/management category |
| **Remote1stJobs** | JSON dump | ✅ | No | Broad; family filter essential |
| **Greenhouse** (employer boards) | JSON API | ✅ | No | Company-specific; must know slugs |
| **Lever** (employer boards) | JSON API | ✅ | No | Company-specific; must know slugs |
| **Ashby** (employer boards) | JSON API | ✅ | No | Fintech/startup heavy |
| **Adzuna** | REST API | ✅ | Yes (free tier) | ZA + global; good salary fields |

#### Greenhouse employer slugs to try (analyst / fintech companies)

Verify each at `https://boards-api.greenhouse.io/v1/boards/{slug}/jobs` before adding to `sources.yaml`:

```yaml
greenhouse:
  employers:
    - {name: "Stripe", slug: stripe}
    - {name: "Plaid", slug: plaid}
    - {name: "Brex", slug: brex}
    - {name: "Carta", slug: carta}
    - {name: "Chainalysis", slug: chainalysis}
    - {name: "Two Sigma", slug: twosigma}
    - {name: "Bridgewater", slug: bridgewaterassociates}
    # Add more after manual verification — slugs change and companies move ATS
```

> ⚠️ **Always verify slugs return HTTP 200 with real jobs before committing.**
> A 404 or empty board wastes Actions minutes and skews health metrics.

#### Lever employer slugs to try

Verify at `https://api.lever.co/v0/postings/{slug}?mode=json`:

```yaml
lever:
  employers:
    - {name: "Palantir", slug: palantir}
    - {name: "Nuveen", slug: nuveen}
    - {name: "Morningstar", slug: morningstar}
    - {name: "FactSet", slug: factset}
    # Verify before adding
```

#### Ashby employer slugs to try

Verify at `https://jobs.ashbyhq.com/api/non-user-graphql` (POST, documented in Ashby adapter):

```yaml
ashby:
  enabled: true
  employers:
    - {name: "Mercury", slug: mercury}
    - {name: "Deel", slug: deel}
    - {name: "Remote.com", slug: remote}
    - {name: "Pipe", slug: pipe}
    # Verify before adding
```

#### Adzuna (optional, free API key)

Register at [developer.adzuna.com](https://developer.adzuna.com) for a free key (no credit card). Set `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` secrets. Then enable in `sources.yaml` and set keyword to `analyst`:

```yaml
adzuna:
  enabled: true
  keywords: "analyst"
  countries: [za, gb, us]
```

#### Sources to leave disabled / never add

| Source | Reason |
|---|---|
| LinkedIn | ToS / anti-bot — explicitly excluded in codebase |
| Indeed | ToS / anti-bot — explicitly excluded |
| Glassdoor | Salary estimates forbidden; anti-bot |
| Workday boards | Undocumented POST endpoints |
| AngelList/Wellfound | No stable public jobs API |

---

### D. Part-Time Detection Rules

#### 1 · Text detection in `config/scoring.yaml`

The `part_time_positive` list in your rewritten `scoring.yaml` (§3) drives detection. Any of these strings in the job title or description count as a part-time signal:

```
part-time, part time, parttime, fractional, contract, freelance,
flexible hours, hourly, per hour, /hr, /hour, remote contractor,
"20 hours", "15 hours", "10 hours"
```

#### 2 · Code change in `src/job_scout/services/scoring.py`

After `ops_hits` scoring (~line 102 in Job Scout), add:

```python
# Part-time / fractional fit (new dimension for Analyst Scout)
pt_hits = _hits(blob, scoring.get("part_time_positive") or [])
pt_weight = float(weights.get("part_time_fit", 8))
breakdown.operations_alt = max(
    breakdown.operations_alt,
    _scale(len(pt_hits), 3, pt_weight),
)
if pt_hits:
    reasons.append(
        f"Part-time / fractional signals detected: {', '.join(pt_hits[:3])}."
    )
```

> **Why reuse `operations_alt`?** `ScoreBreakdown` is a Pydantic model in
> `src/job_scout/models/job.py`. Reusing an existing field avoids a migration.
> If you want a clean model, add `part_time_fit: float = 0.0` to
> `ScoreBreakdown` and reference it in the `total` calculation.

#### 3 · Hourly-rate rule in `src/job_scout/services/salary.py`

The default normalisation in `salary_policy.yaml` contains:

```yaml
normalisation:
  hourly_hours_per_week: 40   # ← Job Scout default
```

**Do NOT keep this at 40 for a part-time scout.** An hourly rate of USD 30/hr at 40 h/week implies USD 5,200/month — but a 15 h/week part-time role at the same rate is only USD 1,950/month. Inflating the figure causes false positives against the salary floor.

**Fix:** Remove `hourly_hours_per_week` from your `salary_policy.yaml` (it is already absent in the template in §4). Then in `salary.py` find the block that converts hourly → monthly and add a guard:

```python
# In salary.py, inside the hourly normalisation branch:
hours_per_week = policy.get("normalisation", {}).get("hourly_hours_per_week")
if hours_per_week is None:
    # Part-time scout: store raw hourly rate; do not annualise.
    # Compare against part_time_hourly.usd_per_hour_floor instead.
    record.salary.hourly_rate = raw_hourly
    record.salary.min_monthly = None   # do not fabricate a monthly figure
else:
    record.salary.min_monthly = raw_hourly * hours_per_week * 52 / 12
```

Then in the salary floor check, add a secondary check:

```python
pt_floor = policy.get("part_time_hourly", {}).get("usd_per_hour_floor")
if pt_floor and record.salary.hourly_rate:
    if record.salary.hourly_rate < pt_floor:
        record.salary.below_floor = True
        record.salary.floor_note = f"Hourly rate {record.salary.hourly_rate}/hr < floor {pt_floor}/hr"
```

---

### 5 · Create a Supabase Project

Follow `docs/SUPABASE_SETUP.md` in full. The schema is identical — you just point the `.env` at a separate Supabase project from Job Scout.

Quick summary:
1. [supabase.com](https://supabase.com) → New project → choose a region close to `af-south-1` (Cape Town) if available, else `eu-west-1`.
2. SQL Editor → run `supabase/migrations/0001_init.sql`, then `0002_...`, then `0003_...` **in order**.
3. Settings → API → copy **Project URL** and **service_role** key.
4. Create `.env` at project root (never commit this file):

```env
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...   # optional; only needed for read-only client

RESEND_API_KEY=re_...
RESEND_FROM=Analyst Scout <analyst@yourdomain.com>
DIGEST_TO=you@youremail.com

JOB_SCOUT_ENV=local
JOB_SCOUT_LOG_LEVEL=INFO
JOB_SCOUT_USER_AGENT=AnalystScout/1.0 (personal job search)
```

---

### 6 · Set Up Resend

1. [resend.com](https://resend.com) → create a free account.
2. **Domains** → add and verify your domain (or use `onboarding@resend.dev` for testing — it only delivers to your Resend account email).
3. **API Keys** → create key → copy to `.env` as `RESEND_API_KEY`.
4. Set `RESEND_FROM` to a verified sender, e.g. `Analyst Scout <jobs@yourdomain.com>`.
5. Set `DIGEST_TO` to your inbox.

---

### 7 · GitHub Actions Secrets + Cron (SAST)

#### Add secrets

Repository → **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | Value |
|---|---|
| `SUPABASE_URL` | Project URL from Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role key |
| `RESEND_API_KEY` | Resend API key |
| `RESEND_FROM` | Verified sender string |
| `DIGEST_TO` | Your email address |
| `ADZUNA_APP_ID` | Only if you enabled Adzuna |
| `ADZUNA_APP_KEY` | Only if you enabled Adzuna |

#### Cron times — prefer the timezone key (do not double-offset)

Upstream Job Scout workflows already use GitHub’s `timezone:` field. **Keep that pattern.** Wall-clock times are then **local SAST**, not UTC:

```yaml
on:
  schedule:
    - cron: "0 10 * * *"
      timezone: "Africa/Johannesburg"   # 10:00 SAST
    - cron: "0 14 * * *"
      timezone: "Africa/Johannesburg"
    - cron: "0 22 * * *"
      timezone: "Africa/Johannesburg"
  workflow_dispatch:
```

Digest at 08:00 SAST:

```yaml
on:
  schedule:
    - cron: "0 8 * * *"
      timezone: "Africa/Johannesburg"   # 08:00 SAST
  workflow_dispatch:
```

**If you omit `timezone`**, cron is UTC and you must subtract 2 hours yourself  
(`0 8 * * *` bare = **10:00 SAST**). That is how digests “run two hours late.” Prefer `timezone: Africa/Johannesburg` and write the local hour you want.

Remove the `USAJOBS_*` environment variables from both workflow files since those adapters are disabled.

---

### 8 · Run Scrape + Digest Locally

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Health check (confirms Supabase connection)
python -m job_scout health

# Dry run — scrapes and prints but does NOT write to Supabase
$env:JOB_SCOUT_DRY_RUN="true"
python -m job_scout scrape

# Live run — writes to Supabase
$env:JOB_SCOUT_DRY_RUN="false"
python -m job_scout scrape

# Preview digest (prints HTML to stdout, does NOT email)
python -m job_scout digest

# Send digest (emails via Resend)
$env:JOB_SCOUT_SEND_EMAIL="true"
python -m job_scout digest --send
```

Expected output for a healthy first scrape:
```
[health]  Supabase OK — jobs table reachable
[scrape]  remoteok         → 12 new  (3 below salary floor, 8 scored Possible+)
[scrape]  remotive         → 7 new
[scrape]  jobicy           → 5 new
[scrape]  himalayas        → 9 new
[scrape]  weworkremotely   → 3 new
[scrape]  remote1stjobs    → 4 new
[scrape]  Done. 40 new jobs stored. Next digest pending.
```

---

### 9 · First Email

```powershell
# One-shot send from local machine (confirms end-to-end)
$env:JOB_SCOUT_SEND_EMAIL="true"
python -m job_scout digest --send
```

Check your inbox within ~30 seconds. The HTML digest groups jobs by fit category (Exceptional / Strong / Good / Possible) with:
- Job title + company + source
- Fit score (0–100) + top reasons
- Salary (if published) — **never invented**
- Apply link
- Part-time signals highlighted if detected

If the email arrives but is empty, the salary floor in `salary_policy.yaml` may be too high for part-time roles, or the scoring threshold (`low_score_cutoff`) is filtering everything out. Lower the floor or set `low_score_cutoff: 40` temporarily to debug.

---

## E. Checklist

Use this before you call the scout "production-ready":

### Setup
- [ ] Fork cloned and renamed (`pyproject.toml` updated)
- [ ] `.env` created with all required keys (never committed)
- [ ] `config/brief.md` filled in (§A complete)

### Config files
- [ ] `config/profile.yaml` — all `TODO` values replaced with real content
- [ ] `config/scoring.yaml` — `professional_positive`, `skills_positive`, `sectors_high` match your brief
- [ ] `config/salary_policy.yaml` — floors set for part-time; `hourly_hours_per_week` **absent** (not 40)
- [ ] `config/sources.yaml` — SA government adapters disabled; analyst remote sources enabled

### Source adapters
- [ ] Remotive `SEARCHES` tuple updated to analyst keywords
- [ ] RemoteOK tags/keywords updated
- [ ] Greenhouse employer slugs verified (HTTP 200) before committing
- [ ] Lever employer slugs verified before committing
- [ ] Ashby employer slugs verified before committing
- [ ] Adzuna enabled only if `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set

### Code changes
- [ ] `scoring.py` — `part_time_positive` hits wired into score (§D step 2)
- [ ] `scoring.py` — replace hardcoded `core_titles` mechanical list + remove `score = max(score, 78)` floor-boost (§G)
- [ ] `salary.py` — hourly → monthly conversion uses `None` guard, not 40 h/week (§D step 3)

### Infrastructure
- [ ] Supabase project created; migrations 0001–0003 applied; tables confirmed
- [ ] Resend account verified; domain or `onboarding@resend.dev` confirmed
- [ ] GitHub repository secrets set (all 5 core + optional Adzuna keys)
- [ ] Workflow cron uses `timezone: Africa/Johannesburg` with the **local** hour you want (or bare UTC with a correct −2h offset — never both)

### Local testing
- [ ] `python -m job_scout health` returns OK
- [ ] Dry-run scrape produces hits without errors
- [ ] Live scrape writes rows to Supabase `jobs` table (confirm in Supabase Table Editor)
- [ ] `python -m job_scout digest` prints HTML without errors
- [ ] First email received with at least one job listed
- [ ] Part-time jobs show part-time signal in digest reasons
- [ ] Hourly-rate jobs do NOT show inflated monthly salary

### Ongoing hygiene
- [ ] Employer ATS slugs re-verified monthly (boards go stale)
- [ ] Salary floors reviewed quarterly (ZAR/USD rate drift)
- [ ] `part_time_positive` list expanded as you notice new signal phrases
- [ ] `unrelated_roles` extended whenever you see obvious false positives in the digest

---

## G. Technical architecture appendix (Job Scout)

> From a full codebase explore. Use this when Claude needs file-level detail.
> Adapters never score, dedupe, write SQL, or send email — only the pipeline does.

### End-to-end

```
scrape (Actions or CLI)
  → iter_adapters(pipeline=remote|hybrid|onsite)
  → RawJobRecord
  → normalise_job (work_mode, geo, salary, mobility)
  → is_family_relevant (profile.yaml job_families) — silent drop if no match
  → apply_hard_filters (validity, geo, salary)
  → DuplicateIndex.merge
  → score_job (scoring.yaml) → fit_score / category
  → Supabase upsert (jobs + job_sources)

digest (separate workflow)
  → list_digest_candidates
  → select new / updated / returning
  → Resend HTML email
  → mark_notified (only after successful send)
```

### Directory map (high signal)

| Path | Role |
|------|------|
| `config/*.yaml` | **Rewrite all four** for the analyst niche |
| `src/job_scout/adapters/base.py` | `SourceAdapter` contract |
| `src/job_scout/adapters/registry.py` | Loads enabled adapters from `sources.yaml` |
| `src/job_scout/adapters/remote/` | Keep — niche-agnostic remote APIs/RSS |
| `src/job_scout/adapters/ats/` | Keep parsers; **replace employer slugs** |
| `src/job_scout/adapters/regional/dpsa_*` / `dws_*` / `dpwi_*` / `sa_pdf_*` / `sanral_*` | **Disable** — SA gov / water niche |
| `src/job_scout/services/dpsa_pdf.py` | **Do not port** to analyst scout |
| `src/job_scout/pipelines/common.py` | Full scrape loop |
| `src/job_scout/services/{normalisation,eligibility,scoring,deduplication,database,email_digest}.py` | Mostly niche-agnostic; scoring keywords come from YAML |
| `supabase/migrations/0001–0003` | Apply in order on a **new** Supabase project |
| `.github/workflows/{scrape,digest,health}.yml` | Cron with `timezone: Africa/Johannesburg` |

### Models

- **`RawJobRecord`** — adapter output (`title`, `company`, URLs required).
- **`NormalisedJobRecord`** — typed geo / salary / mobility + fingerprint.
- **`CanonicalJobRecord`** — persisted + `fit_score`, `rejected`, `last_notified_at`.

### Config rewrite priorities

1. `profile.yaml` → `job_families` (gates relevance; wrong list ⇒ zero jobs).
2. `scoring.yaml` → all `*_positive` / `sectors_*` / `unrelated_roles` lists.
3. `salary_policy.yaml` → floors; delete `public_service` OSD block.
4. `sources.yaml` → disable SA gov; swap ATS employers; remote-first pipelines.

### Hardcoded Python to fix (YAML alone is not enough)

In `src/job_scout/services/scoring.py` (~lines 195–205):

```python
core_titles = (
    "mechanical engineer",
    "mechanical design",
    # ...
)
if any(token in title for token in core_titles) and breakdown.sector >= 4 ...:
    score = max(score, 78)  # forces Good for mechanical titles
```

For Analyst Scout: replace `core_titles` with analyst variants **or remove the floor-boost** entirely so analysts are not stuck with mechanical bias / inflated scores.

### Secrets

Always: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.  
Digest: `RESEND_API_KEY`, `RESEND_FROM`, `DIGEST_TO`.  
Optional: `ADZUNA_*`, `USAJOBS_*`.  
Local: copy `.env.example` → `.env`. `JOB_SCOUT_DRY_RUN=true` uses in-memory repo (no Supabase write).

### What stays verbatim

Pipeline orchestration, normalisation, eligibility structure, dedup, FX (Frankfurter), digest HTML/Resend, HttpClient, registry — these are niche-agnostic once config + the scoring hardcoded block are fixed.

---

*Architecture reference: `src/job_scout/` — adapters → pipelines → Supabase (`services/database.py`) → morning HTML digest via Resend (`services/email_digest.py`). Public APIs and RSS only. No LinkedIn, no Indeed, no scraping behind login walls.*
