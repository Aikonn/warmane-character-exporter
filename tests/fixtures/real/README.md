# Real-response fixtures (Milestone 0)

Small samples of live Warmane armory responses retrieved on 2026-10-24 through the maintainer's own browser (a handful of manual requests; no automated crawling). They are factual game data (character names are public armory pages) and are kept minimal.

| File | Request | Notes |
|---|---|---|
| api-summary-aikka-onyxia.json | GET /api/character/Aikka/Onyxia/summary | Priest, 17 items, two specs |
| api-summary-bezduse-icecrown.json | GET /api/character/Bezduse/Icecrown/summary | Death Knight, 16 items, empty guild and pvpteams |
| achievements-92-sample-aikka-onyxia.json | POST category=92 on /character/Aikka/Onyxia/achievements | Trimmed to 2 earned and 2 locked entries; wrapper {"content": html} |
| statistics-130-aikka-onyxia.json | POST category=130 on /character/Aikka/Onyxia/statistics | Complete response |

Full HTML page captures stay in the git-ignored local-captures folder. Do not add the full captures or third-party site scripts to the repository.