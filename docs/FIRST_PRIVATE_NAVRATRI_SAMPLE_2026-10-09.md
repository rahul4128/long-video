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

## Google Flow clips — prepared for ChatGPT Work, not generated here

**IMPORTANT:** Google Flow Free is only accessible through its authenticated UI in a separately opened permitted browser session. GitHub Actions cannot automatically generate clips from Flow; Work must create/export them first. Do not claim credits were used without an actual successful Flow export. Set clips without identifiable real people or logos. Keep shots 5–10 sec, photorealistic, natural camera movement, no subtitles, no captions, no music baked into the clip, no lip sync. Narration and licensed music are added later by our pipeline.

### FLOW PROMPT — Long hook (16:9, export as hook-long.mp4)

"Photorealistic cinematic 16:9 eight-second festival documentary B-roll, respectful joyful Navratri night in Gujarat, wide circular Garba dance formation with a diverse group of Indian adults in detailed colorful traditional Gujarati festive outfits, rhythmic coordinated footwork and twirling, rich red, gold and turquoise decorations, hanging warm lantern lights, natural crowd movement, camera glides dynamically sideways then gently rises to reveal the whole glowing circle, genuine documentary realism, high-quality faces and hands, culturally credible dance attire, visually striking first frame, sharp details and pleasing motion blur, no copyrighted logos, no written text, no subtitles, no watermark, no generated dialogue, no music audio, no overly rapid jump cuts, no unsafe action. Do not depict a specific real event or real person."

### FLOW PROMPT — Shorts hook (9:16, export as hook-shorts.mp4)

"Photorealistic vertical 9:16 eight-second cinematic documentary B-roll of a West Bengal Durga Puja decorated public pandal during evening festivities, expressive visitors in elegant contemporary Bengali festive outfits looking upward with wonder, elaborate floral and fabric decorations, respectful visually accurate Durga iconography when visible, warm festive lights, crowd in the background and lively movement, camera starts very close to illuminated colorful decorations and pushes forward to reveal the full majestic pandal interior, vibrant but realistic composition, dynamic attention-grabbing first second, sharp faces and clean detailed hands, no written text, no subtitles, no watermark, no copyrighted signage, no generated speech or music. Fictional generic scene, not a documentary claim about a particular real location."

## Required handoff to render

1. Produce **approved structured payload JSON** with the existing Make Final Judge schema (6 Long scenes and 5 Shorts scenes) for this exact editorial concept. Do NOT send `{}` as payload; that invokes irrelevant fallback.
2. In signed-in Google Flow UI, export the two specified MP4s and confirm filenames, orientation and cultural accuracy. Use only free credits if available.
3. Publish those MP4s as assets in a NEW GitHub Release at `https://github.com/rahul4128/long-video/releases`. Do not invent URLs; record exact returned asset URLs.
4. In GitHub Actions `.github/workflows/render.yml` on branch `office-make-clone`, run manually with `payload` set to the approved JSON, `flow_clips_json` containing the **actual two GitHub Release asset URLs**, `flow_clips_strict=true`, and `privacy=private`.
5. Check `out/flow_clip_report.json` for `applied` entries in Long scene 1 and Shorts scene 1; watch both outputs and inspect Hindi narration, subtitles, music rights, factual clarity and thumbnail. A private YouTube upload occurs only if the separately configured webhook is active; never claim an upload from a successful render alone.

If private YouTube upload settings or release MP4s are not confirmed, **stop before rendering**. Do not activate production scenario or publicly publish anything.
