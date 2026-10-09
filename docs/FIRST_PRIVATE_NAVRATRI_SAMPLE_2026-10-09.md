# First private video sample — Navratri: one festival, three vibrant celebrations

**Date:** 2026-10-09 (India)  
**Mode:** Editorial sample brief only. No auto-upload; Production Make scenario 7722792 remains inactive.  
**Working theme:** Festivals through human curiosity, excitement, social belonging, delight, meaningful traditions. Garba is just one example, not a universal content quota.

## Editorial selection (more visually exciting than the repeated ritual-checklist or calm room-setup variants)

**Long Hindi title (candidate):** एक नवरात्रि, तीन अनोखे जश्न! कहीं गरबा, कहीं पंडाल, कहीं गोलू  
**Shorts Hindi title:** एक नवरात्रि, भारत में 3 अलग जश्न!  
**Mobile thumbnail:** एक पर्व, 3 जश्न!  
**Hook:** "तीन जगहें, तीन बिल्कुल अलग नज़ारे… लेकिन त्योहार एक ही — नवरात्रि! आखिर ऐसा क्यों?"

This is a **human editorial preference for the first test**, NOT an output the Make Critic already approved. Re-run the council against this concept and obtain its approved, fully structured render JSON before using GitHub Actions. The previous A/B safe tests generated diverse alternatives but still sometimes approved overused "3 puja mistakes" titles.

### Grounded facts and boundaries

- **Gujarat:** Garba is a circular, energetic community dance and important part of Navratri celebrations. [Incredible India / Gujarat Tourism](https://www.incredibleindia.gov.in/en/festivals-and-events/gujarat/Vibrant-Navratri-Festival-2026)
- **West Bengal:** Durga Puja is celebrated with creative pandals, decorated idols, cultural gatherings and festivities. [West Bengal Tourism](https://wbtourism.gov.in/durgapuja)
- **Tamil Nadu:** Navarathiri Golu/Kolu includes stepped displays of dolls and figurines often arranged to depict religious/cultural stories, along with visits and singing. [India Ministry of Tourism Utsav](https://www.utsav.gov.in/view-event/navarathiri-festival)
- **India overall:** Regional Navratri celebrations differ and can include dance, Durga Puja, and Golu. [Incredible India](https://www.incredibleindia.gov.in/en/festivals-and-events/navratri)
- Distinguish **cultural traditions** from universal requirements. Do not invent ancient-warrior origins for dance, make medical/wealth miracles, fake regional costumes or misleading geography. Do not use copyrighted commercial Garba songs without licensing. Tithis and location-specific muhurat require separate verification.

## Retention-first Long outline (6 scenes, target 150–210 sec)

1. **0–5s hook / Scene 1:** Rapid visual contrast: brightly colored Gujarat festival dancers, Kolkata pandal decorations, Tamil Nadu Golu figurines. Ask how they can belong to one festival. Promise three distinctive answers and a surprising emotional connection.
2. **Gujarat:** Dynamic, respectful Garba circle; communal energy, colorful chaniya cholis and kediyu-style festive attire where suitable. Explain that people celebrate together through dance. Do not claim all Indians dance Garba.
3. **West Bengal:** Artistic pandal walk-through, joyful families and beautifully crafted Durga idol (avoid synthetic misrepresentation of deity details); cultural and artistic significance of public celebrations.
4. **Tamil Nadu:** Authentic stepped Golu doll display in a home, family/neighbor visits, stories told with figurines. Respect miniature scale and arrangement; show this as a cultural example, not a universal must-do.
5. **Common meaning:** Split the screen across joyous community dance, imaginative craft and gatherings. Connect the viewer to shared belonging and different regional expression; avoid declaring the practices historically identical.
6. **Payoff + follow-up:** Three approaches, many shared emotions: connection, creativity, devotion. Ask viewers which version they have actually experienced. Tease a *specific sourced* festival custom for the next episode.

**Long storytelling rule:** Six spoken-Hindi scenes according to the exact production schema. Use changing visual scenes and earned payoffs every ~20–30 seconds. No generic "आज हम बात करेंगे" greeting. Render ONLY after the Critic and independent reviewer approve this same idea.

## Independent Short outline (5 scenes, target 25–35 sec)

1. "नवरात्रि में कहीं नाचते हैं, कहीं भव्य पंडाल बनते हैं, कहीं गुड़ियों की सीढ़ियां सजती हैं — क्यों?"
2. Gujarat — energetic Garba celebration.
3. West Bengal — elaborate Durga Puja artistic pandal.
4. Tamil Nadu — stepped Golu display and home visits.
5. "जश्न अलग, जुड़ाव एक!" Invite an authentic regional story in comments.

The Short must completely answer its own question and not be a teaser requiring the Long.

## Existing pipeline — updated 2026-10-10

User removed Google Flow from this sample. Use the existing Kokoro narration, stock footage matching, AI image fallback, captions, thumbnails and Remotion render pipeline. No external hook MP4s or preliminary clip Release are required.

Keep both Make scenarios paused; do not run further Make retries for this preparation.

## Required handoff to render

1. Prepare and review a fully structured production-schema payload for this same concept (6 Long scenes, 5 Shorts scenes). The outline above is not an approved payload. Never dispatch an empty payload.
2. Use .github/workflows/render.yml on office-make-clone with privacy=private, flow_clips_json empty, and flow_clips_strict=false. Empty Flow input preserves the original stock/AI asset generation.
3. Inspect content QC and final media QC, then watch both outputs for Hindi narration, captions, regional accuracy, visual relevance and pacing.
4. Verify the upload webhook honors privacyStatus=private before permitting a YouTube upload. The workflow publishes downloadable GitHub Release assets independently of YouTube privacy; do not call these private assets without checking repository visibility.

Current status: brief updated; no sample render dispatched; no approved structured payload saved by this update. Production stays paused.
