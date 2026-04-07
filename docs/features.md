# Features

This document describes the user-facing capabilities of the Consumer Duty Sludge Audit Tool.

## Core workflows

### Single-site audit

Submit a single public website URL and receive a structured Consumer Duty report covering PRIN 2A.2–2A.5:

- outcome-level scores (0–10) and RAG bands
- criterion-by-criterion scoring with supporting evidence
- findings with severity, verbatim evidence, page URL, and FCA reference
- outcome-specific recommendations

#### The four outcomes (PRIN 2A.2–2A.5)

The report covers the four FCA Consumer Duty outcomes:

- **Products & Services (PRIN 2A.2)**: product and service design/distribution signals, target market framing, and whether material risks and limitations are signposted.
- **Price & Value (PRIN 2A.3)**: pricing/charges discoverability and clarity, and whether value framing is consistent with the price information presented.
- **Consumer Understanding (PRIN 2A.4)**: whether communications support informed decisions (clarity, layering, balanced risk/benefit, and decision support cues).
- **Consumer Support (PRIN 2A.5)**: whether support is easy to find and effective (complaints, ease of exit, vulnerable customer support, and accessibility/alternative formats).

Where appropriate, **Products & Services** and **Price & Value** are treated as **public-evidence-only** and flagged as partial where internal firm data would be required for a complete view.

### Two-site comparison

Compare two websites side-by-side to see how their outcome scores and findings differ. This is intended for:

- competitor benchmarking
- before/after comparisons during remediation
- comparing a firm’s site against a peer set

### User journey audit

Define a specific journey as an ordered list of URLs (for example: homepage → product page → application → support). Each step is fetched and assessed for:

- friction signals (journey-specific obstacles that indicate customer effort)
- suspected dark patterns, with verbatim evidence quotes

This complements the full-site audit: the journey audit is path-specific; the full audit is breadth-first across the site.

## Report experience (what users see)

### Outcome cards

For each outcome, the report presents:

- score (0–10) and RAG band
- confidence level with an explanatory confidence note
- a short outcome summary
- an expandable scoring breakdown

Where applicable, the report labels outcomes that are **public-evidence-only** (partial by design).

### Scoring breakdown and evidence

Each outcome includes a checklist breakdown showing:

- awarded points per criterion
- whether the criterion is met
- the exact evidence text extracted from the audited site
- the page URL where the evidence was observed

### Findings and recommendations

Findings are presented with:

- severity (critical / moderate / minor)
- verbatim evidence text
- FCA reference (grounded in retrieved regulatory sources)
- the source page URL

Recommendations are listed per outcome to support remediation planning.

### Site-wide navigation aids

The report includes:

- a page-level friction map across crawled pages and outcomes (pass / partial / fail signals)
- a consolidated list of suspected dark patterns
- a consolidated list of vulnerability support gaps (where detected)

### Downloadable report

Reports can be printed/downloaded from the UI for sharing and review.

## Operational features

### Caching and deep links

Audits are cached by URL key to support repeatable access and reduce rework during iteration. Cached reports can be reopened via deep links (for example, `/report?url=…`).

### API endpoints

The backend provides endpoints for:

- running audits
- retrieving cached reports
- comparisons (run and retrieve)
- journey audits
- cache management

See `README.md` for quickstart and example API usage.

