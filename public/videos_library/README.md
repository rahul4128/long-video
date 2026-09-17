# Local curated video library (5th fallback tier)

This folder is the "guaranteed correct clip" tier for niche devotional /
mythological scenes. Pexels, Pixabay, and Coverr are all general-purpose
**Western** stock libraries — they have thin-to-no coverage
of Sanskrit/Hindi terms or mythological proper nouns (Krishna, shankh,
aarti, Kurukshetra, Sudarshan Chakra...). `generate_assets.py` now rewrites
those terms into broader English phrases before searching (see
`NICHE_TERM_REWRITES` / `build_query_candidates()`), which fixes a lot of
"wrong clip" cases — but a keyword search still isn't guaranteed to be
*your* clip.

This folder lets you pin an exact, hand-picked clip to a keyword once, for
free, and reuse it forever — no API key, no per-run search, no risk of the
wrong clip.

(There's also now a 4th automatic search source, Wikimedia Commons —
completely free, no key needed, and it actually hosts real Indian
temple/festival/ritual footage. It's tried automatically before this
folder, so you may find you don't need to add many files here at all.)

## How it works

`fetch_local_library_video()` in `generate_assets.py` is tried automatically
as the last resort before the pipeline falls back to an AI-generated still
image. It looks at every word in the scene's `videoSearchQuery` +
`imagePrompt`, and for each one checks whether a file in this folder
**starts with that word** and ends in `.mp4`. First match wins.

- `diya.mp4` → used for any scene whose query/prompt contains the word "diya"
- `diya_1.mp4`, `diya_2.mp4`, `diya_3.mp4` → same, but one is picked at
  random each time so repeated diya scenes don't all look identical
- `krishna.mp4`, `temple.mp4`, `conch.mp4`, `chariot.mp4`,
  `battlefield.mp4`, `aarti.mp4` → same pattern for your other recurring
  terms

## Where to source clips (free, no scraping, no API needed)

Download a handful of clips manually (once) from any of these — all offer
free downloads under licenses that permit this kind of reuse without a paid
plan:

- **Mixkit** (mixkit.co/free-stock-video) — free, no attribution required
- **Videvo** (videvo.net) — free tier, check each clip's specific license
- **Videezy** (videezy.com) — free tier (some clips require free
  attribution — read the individual clip's license)
- Your own Pexels/Pixabay downloads for a specific clip you know looks right

Rename the file to match the keyword(s) you want it to answer to and drop
it in this folder. Nothing else needs to change — no code, no secrets, no
extra API key.
