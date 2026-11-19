# Job Scout: gap research and roadmap (19 Nov 2026)

What the scraper covers, what it misses, which job sources exist for a mechanical / QA-QC /
civil-water engineer targeting the US (EB-2 / EB-3) and South Africa, and what to do next.
Every source below was tested live with plain, honestly identified requests; sites that
refuse automated clients are listed as blocked and are **not** worked around.

---

## 1. Where it stands

Measured on the live dashboard before this round of changes (404 open jobs):

| Signal | Value | What it means |
|---|---|---|
| Top 5 employers' share | ~170 of 404 (Crusoe alone 58) | Results lean on a handful of cleantech start-ups whose boards happen to be open |
| South Africa | 5 jobs | SA coverage is almost nil (DPSA/DWS block cloud runners; SA consultancies have no open boards) |
| Posted > 30 days ago | 131 | A third of listings are old; freshness is not used in ranking |
| Same job, several cities | 18 groups / 26 extra cards | Noise (fixed: now one card with "+N locations") |
| Visa status unknown | 230 | Most US adverts say nothing about visas |
| Green-card sponsor history | 156 | PERM data (added earlier today) is the strongest visa signal available |
| Salary not published | 159 | Allowed since today's policy change |

## 2. Weak spots found and fixed in this round

| Problem | Evidence | Fix |
|---|---|---|
| "Visa Sponsorship Available: No" read as **sponsors** | Black & Veatch adverts carry this field; the free-text regex matched "sponsorship … available" | Structured Yes/No fields are read first (also "Relocation eligible: Yes/No") |
| Indian / Colombian jobs treated as **US** | "Pune, MH, IN" → Indiana, "Bogota, co" → Colorado (SmartRecruiters, SuccessFactors) | Source country codes override text; "City, State, CC" reads the last part as the country |
| ITAR / defence employers via aggregators | SpaceX appeared through Adzuna (snippet hides "U.S. person") | `exclude_employers` in profile.yaml (SpaceX, Anduril, Lockheed, Northrop, RTX, …) applied to every source |
| Academic, intern, graduate and "AI evaluator" posts | NSPE carries faculty posts; "mechanical" in the title protected them | `exclude_titles.always` (not overridable) |
| Duplicate multi-city cards | AECOM "Industrial Mechanical Engineer" ×5 | Dashboard groups by title + employer |
| Huge boards eat the time budget | SGS (4,500 postings) + AECOM in one source took 257 s | SmartRecruiters keyword/country searches; SGS has its own source and budget |

## 3. Source landscape

### Added today (verified live)

| Source | Type | Why it matters | Live result |
|---|---|---|---|
| Black & Veatch, Hatch, Sasol | SuccessFactors career-site RSS | Water/power EPC (US), global engineering, SA petrochemical | 192 jobs, 138 relevant |
| GHD | Oracle Recruiting Cloud JSON | Global water/infrastructure consultancy, US + AU + ZA | 22 senior roles with full descriptions |
| NSPE Career Center | Association job board (RSS) | US professional-engineer board, broad employer mix | 116 jobs, 97 relevant |
| SGS | SmartRecruiters (keyword search) | World's largest inspection/QC firm: welding, source, petroleum inspectors | 137 US inspector postings available |
| Olsson, Burgess & Niple | Greenhouse | US civil/water consultancies (Olsson lists API 510/570 inspector roles) | 348 + 61 postings |

### Blocked (tested, refused automated access, not worked around)

| Source | Response | Note |
|---|---|---|
| AWWA, ASCE, ASQ, ASME, ASHRAE career centres | 403 | Same YM Careers platform as NSPE, but bot protection is on. Worth email job alerts by hand |
| The Muse API | 403 | |
| AcademicKeys | 403 | |
| dol.gov downloads | 403 to scripts | PERM file downloaded through the browser instead |
| Workday wd3/wd5 tenants (Xylem, HNTB, GE Vernova, Stantec/MH, Mueller, Badger) | 429 to all automated clients | Only Primoris (wd108) answers |
| DPSA, DWS | 403 to GitHub runners | Skipped in CI; would work from a South African connection |
| Jacobs, Fluor, Worley, AtkinsRéalis, KBR, Stantec, Arcadis, Mott MacDonald career sites | Phenom / SuccessFactors with feed disabled / Cloudflare | No open feed found |

### Not allowed or not useful

| Source | Reason |
|---|---|
| LinkedIn, Indeed, Glassdoor, ZipRecruiter | Terms of service forbid scraping; anti-bot. (Tools like JobSpy scrape them anyway; deliberately not used) |
| USAJOBS | Federal jobs require US citizenship, useless for a visa applicant |
| PNet, CareerJunction, Careers24 (SA) | No public API/feed; HTML scraping not permitted |
| HigherEdJobs | 239 RSS feeds, none for engineering/facilities |

### Needs a free key from you (not added yet)

| Source | What it adds | Sign-up |
|---|---|---|
| **Jooble** | Large aggregator with a free REST API (US + ZA); fills gaps from employers on blocked ATSs | jooble.org/api/about |
| **Careerjet** | Aggregator API (affiliate ID) with ZA and US coverage | careerjet.com/partners/api |

Both would broaden reach into the big consultancies whose own sites are closed. Adzuna already
proves the pattern (617 raw jobs per run).

## 4. What the visa routes mean for the search

*Not legal advice; confirm with a US immigration attorney.*

- **EB-3 (and EB-2 with a job offer) need an employer to file PERM labor certification.**
  The best predictor is whether the employer has done it before for engineers; that is what
  `config/visa_sponsors.csv` (DOL PERM FY2025–26, 8,798 employers) measures. Rebuild it yearly.
- **EB-2 National Interest Waiver (NIW) and EB-1A are self-petitions**: no employer, no PERM.
  EB-2 needs an advanced degree, and a bachelor's plus five years of progressive experience
  counts as one. With water-infrastructure and dam leadership experience this route may not
  depend on the job search at all. Worth an attorney consult.
- **H-1B** is lottery-based for most employers. **Cap-exempt employers** (universities, their
  affiliated non-profits, non-profit and government research organisations) skip the lottery,
  so university facilities/utilities engineering roles are unusually reachable. In September
  2025 a presidential proclamation added a $100,000 payment for many new H-1B petitions for
  workers outside the US; check whether it still applies, because it makes direct green-card
  sponsorship relatively more attractive to employers hiring from abroad.
- **Signals the scraper now reads:** stated sponsorship (incl. H-1B / green card / PERM / EB-2/3
  wording), structured "Visa sponsorship available: Yes/No" fields, "no sponsorship" phrasing,
  ITAR "U.S. person" requirements, and PERM history per employer.

## 5. Remaining weak spots and roadmap

Ordered by expected gain per hour of work.

1. **Jooble / Careerjet keys** (you sign up, ~10 min). Adds the large consultancies and utilities
   that only post on closed career sites.
2. ~~**Freshness in the score.**~~ Done in this round: +3 for adverts under 7 days old, −4 after
   30 days, −10 after 60 (jobs with a future closing date are untouched). Tunable under
   `freshness` in `config/scoring.yaml`.
3. **Cap-exempt flag.** Mark universities and non-profit research employers (from employer name
   + PERM data) so H-1B-lottery-free roles stand out.
4. **More Oracle / SuccessFactors employers.** The two new adapters only need a host + site per
   employer. Candidates to check: AECOM's and Jacobs' regional sites, Aurecon, Zutari, SMEC,
   Worley regional, Eskom, Rand Water, Umgeni-uThukela, TCTA.
5. **South Africa from home.** DWS works from a South African connection. A weekly Windows
   Task Scheduler job on your PC running `python -m job_scout scrape` with the CI-skipped
   sources would restore DWS (DPSA also refused requests from this PC during testing).
6. **Application tracking.** "Seen" is per-browser only. Moving it (plus "applied", "rejected",
   notes) into Supabase would make it follow you across devices and let the email skip jobs
   you have already handled.
7. **Alerts for top matches.** A same-day email or push for Exceptional jobs at known sponsors
   instead of waiting for the 08:00 summary.
8. **Middle East and Australia** (optional): Gulf water/desalination and Australian
   infrastructure hire mechanical/water engineers on employer-sponsored visas. GHD and Hatch
   already return AU jobs; the Gulf is not searched at all.

## 6. Adding employers yourself

| Platform | Find it in the careers URL | Config (`config/sources.yaml`) |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/<slug>` | `greenhouse.employers: - {name, slug}` |
| Lever | `jobs.lever.co/<slug>` | `lever.employers` |
| Ashby | `jobs.ashbyhq.com/<slug>` | `ashby.employers` |
| SmartRecruiters | `jobs.smartrecruiters.com/<Slug>` | `smartrecruiters.employers` (optional `queries`, `countries`) |
| SuccessFactors | `<host>/job/...`; test `https://<host>/services/rss/job/?keywords=engineer` | `successfactors.sites: - {name, slug, host}` |
| Oracle Cloud | `<host>/hcmUI/CandidateExperience/en/sites/<site>/` | `oracle_cx.employers: - {name, slug, host, site, countries}` |
| Workday | `<tenant>.<pod>.myworkdayjobs.com/<site>` | `workday.employers` (most tenants block automation) |

Sources: [DOL PERM performance data](https://www.dol.gov/agencies/eta/foreign-labor/performance),
[NSPE Career Center](https://careers.nspe.org/),
[SAP: SuccessFactors job feeds](https://learning.sap.com/courses/sap-successfactors-recruiting-candidate-experience-academy/generating-xml-feeds-to-support-the-customer-s-job-distribution-requirements_c23ea68c-3e00-4011-8525-2c9f550ee8a7),
[AWWA Career Center](https://careercenter.awwa.org/).
