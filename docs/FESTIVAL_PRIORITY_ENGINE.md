# Date-verified Festival Priority Engine (2026)

This is the shared, public read-only calendar source for **Primary Performance Sync 7726647** and **Primary Video Generator 7722792**.

## Integration

- JSON source: `data/festival_routes_2026.json` on `office-make-clone`.
- Performance Sync: **HTTP module 126** downloads the source, **Gemini module 109** consults the India-local date route before using historical YouTube metrics to recommend the next episode.
- Generator: **HTTP module 909** downloads the same source, Agents **907, 908, 51** rank date-specific youth entertainment (Garba/Dandiya, food, outfits, live festival experience) alongside devotional utility/rituals, emotions and credible excitement.
- Generator **filter on module 40** retains its 6 Long scenes, 5 Shorts scenes, Hindi-title and QC PASS checks AND requires that the Long title match the festival-specific `title_regex` when a verified date route exists.
- The generator is **inactive/paused** until the user approves a test; neither the calendar commit nor these edits dispatch YouTube uploads.

Make uses the current IST calendar date to select `daily[YYYY-MM-DD]`. The daily route carries festival start/end, event phase, source, and possible content lanes; **none of the content scripts are fixed**. The AI should select what best benefits users, and the title gate prevents an unrelated recommendation from being published during a verified festival.

## Today's intended outcome

2026-10-09: Navratri **preparation**, not generic daily puja or temple engineering. Dynamic contenders include Garba first-timer/steps, affordable dress, Dandiya etiquette, kalash/puja setup, bhog, family questions, meaningful storytelling and original cultural/entertainment angles.

2026-10-11 through 2026-10-19: relevant **in-festival** material; different creator angle each day. 2026-10-19 is the final observance day in this source; 2026-10-20 is Vijayadashami. Exact tithi counts and muhurats are location-dependent and **must be checked**. 2026-11-13 through 2026-11-16 covers all four Chhath phases.

## Maintenance and safeguards

This calendar is **verified for its finite date range only: 2026-09-27 through 2026-11-24**. To cover later Indian holidays or 2027 and beyond, a maintainer must verify dates against reliable regional sources and extend the `daily` collection and `sources` list. The source doesn't pretend to compute lunar tithis automatically. On unlisted dates, Make's title filter accepts evergreen content but Gemini should still research the next 14 days of upcoming festivals via live evidence, and label uncertain claims for verification.

Add at least one **youth/fun/social celebration** option and one **practical/meaningful** option for each festival, but let daily topic selection remain dynamic. Claims of divine punishment, guaranteed money/health outcomes, fear manipulation or use of unlicensed Garba songs are prohibited. The intent is real clicks, watch time, likes and subscribers through useful, appealing videos.

The GitHub Action **Test Festival Priority Calendar** checks route transitions, date/source coverage, availability of youth Garba lanes, title gate rejection of generic topics, and public URL availability. A green test validates the **calendar data**, not Make runtime execution or Gemini's compliance. Do not unpause the generator without a controlled validation after changing Make mappers.
