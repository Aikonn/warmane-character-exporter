# Real-response fixtures (Milestone 0)

Small samples of live Warmane armory responses. Most were retrieved on 2026-10-24 through the maintainer's own browser; later additions identify their retrieval method and date. The fixtures are factual game data and are kept minimal.

| File | Request | Notes |
|---|---|---|
| api-summary-aikka-onyxia.json | GET /api/character/Aikka/Onyxia/summary | Priest, 17 items, two specs |
| api-summary-bezduse-icecrown.json | GET /api/character/Bezduse/Icecrown/summary | Death Knight, 16 items, empty guild and pvpteams |
| api-summary-not-found-onyxia.json | GET /api/character/Qzxqzxqzxqzx/Onyxia/summary | HTTP 200, 37-byte JSON object with `error: "Character does not exist."`; one user-approved live request on 2026-11-15 |
| achievements-92-sample-aikka-onyxia.json | POST category=92 on /character/Aikka/Onyxia/achievements | Trimmed to 2 earned and 2 locked entries; wrapper {"content": html} |
| statistics-130-aikka-onyxia.json | POST category=130 on /character/Aikka/Onyxia/statistics | Complete response |

Full HTML page captures stay in the git-ignored local-captures folder. Do not add the full captures or third-party site scripts to the repository.

For the not-found response, the observed API error object is distinct from transport access errors: HTTP 403 with an Error 1010/access-denied body is a block, while HTTP 429 or rate-limit content such as Error 1015 is a rate limit (the page marker does not itself specify the HTTP status). Do not classify arbitrary JSON errors as not-found; only this exact source response has been verified.

The not-found fixture was captured 2026-11-15 from the Onyxia armory with one owner-approved, budgeted GET using the project's fetch transport. Its purpose is to document the not-found response shape; the ruleset is not applicable to this error-only response. Sanitization retains only the minimal generic JSON body; no headers, cookies, or personal data are included.