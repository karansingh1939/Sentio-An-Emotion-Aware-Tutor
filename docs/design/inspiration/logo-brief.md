# Sentio logo brief

- **Date:** 2026-11-03.
- **Status:** brief for a designer or an image tool. Not made yet.
- **Decision:** the name stays **Sentio**.
- **References from Karan:**
  - [wordmark-reference-tesla.png](wordmark-reference-tesla.png): Tesla's wordmark, for the style of the lettering.
  - Apple's logo, for the idea of a single stand-alone symbol. Shared in chat; not saved as a file.
- **The rule:** take the spirit of these references, never their shapes.

## What the references show

**Tesla wordmark (lettering):**

- All capitals in a wide, geometric, custom-drawn face; nothing taken from a stock font.
- Very generous letter spacing, roughly a letter's width between letters.
- One thin, even stroke weight.
- Letters simplified to their essentials: the E is three separate bars with no upright; the A is an open arch with no crossbar.
- Flat, single colour, no effects. It reads as engineered, calm and expensive.

**Apple logo (symbol):**

- One solid, filled shape with no text and no outline.
- Recognisable from its silhouette alone, from a 16px icon to a billboard.
- One small, deliberate detail makes it ownable (Apple's is the bite and the leaf).
- Works in black, in white and in one brand colour.

## The Sentio wordmark

- **Letters:** `S E N T I O` in capitals, custom-drawn, wide and geometric, with one thin even stroke.
- **Spacing:** generous, around 0.6–0.8 of a letter's width between letters.
- **Simplify each letter the way Tesla does, without copying Tesla's letters:**
  - **S:** built from three horizontal strokes joined by short verticals at alternate ends, squared rather than curved.
  - **E:** three short horizontal bars. Make it distinct from Tesla's: for example, a shorter middle bar or a single thin upright.
  - **N:** two uprights and one diagonal, with no serifs.
  - **T:** one crossbar and an upright, perhaps with a small gap where they meet.
  - **I:** a single upright.
  - **O:** a rounded rectangle (stadium shape) rather than a circle, so it matches the squared S and E. Optionally leave one small gap.
- **Colour:** graphite (`#202938`) on light backgrounds, chalk (`#edf0f7`) on dark. Ink Indigo (`#465bb2`) only if the wordmark is used alone.
- **No effects:** no gradients, glows or outlines, matching DESIGN.md.

## The Sentio symbol

One solid shape that stands alone, as Apple's does, and says what Sentio is: answers taken from your own pages, cited.

Directions for a designer to explore:

1. **The page.** A solid rounded page silhouette with one folded corner, the right-hand page of a book.
2. **The O.** The stadium-shaped O from the wordmark as a filled shape, with its gap read as a page corner or a citation mark.
3. **The citation.** A solid page with a small notch at the foot, echoing the citation chips in the app.

**Requirements:**

- One filled shape, no text inside.
- Recognisable at 16px (browser tab), 32px (sidebar) and 512px (app icon).
- Works in black, white and Ink Indigo.
- No brain, lightbulb, graduation cap or sparkle. Those read as generic "AI" or "edtech".

## Where they're used

- **Sidebar:** the symbol at 32px, plus the wordmark. This replaces the indigo square with an "S".
- **Sign-in page:** the symbol, with the wordmark above the form. This replaces the 🧠 emoji.
- **Browser tab icon:** the symbol on its own.
- **Landing page, README and screenshots:** the wordmark.

## Prompt for an image tool

> Minimal logo for a study app called "SENTIO". Wordmark: all capitals, custom extended geometric letterforms, thin uniform stroke, very wide letter spacing, letters reduced to essential strokes (the E as horizontal bars, the O as a rounded rectangle), flat graphite colour on white, no gradients, no effects. Separately, a single solid symbol: a simple filled page silhouette with one folded corner, recognisable at 16px, flat, one colour. Clean vector style, centred on a white background. Do not reproduce any existing brand's letterforms.

Treat anything an image tool generates as a draft. Have the final logo redrawn as clean vectors (SVG) before using it in the app.

## Drafts round 1 (2026-11-03)

- **Made with:** Figma's image tool (`gpt-image-2.5-flare`), in the Figma file [Sentio logo drafts](https://www.figma.com/design/3l32SdeF4ZIYRLF2WqSAS0). Two images; this used Figma AI credits.
- **Copies:** saved in `logo-drafts/`, because Figma's download links expire after 7 days.

### Wordmark: [wordmark-draft-1.png](logo-drafts/wordmark-draft-1.png). Keep this direction.

**What works:**

- It reads clearly as SENTIO.
- Thin, even stroke and very wide spacing; it feels engineered and calm, as the brief asked.
- The letters are its own, not Tesla's:
  - the S is squared;
  - the E keeps its upright and has a shorter middle bar;
  - the O is a rounded rectangle.

**What to fix in the vector redraw:**

- The gaps between letters are uneven: E–N and I–O look wider than S–E. Space by eye, not by measurement.
- The corners don't match. The S and E are sharp-cornered, while the O's corners are noticeably round. Pick one radius and use it everywhere, or keep sharp corners and give the O only a small radius.
- The stroke weight wobbles slightly, as is normal for a generated image. Redraw on a grid with one fixed stroke width.

### Symbol: [symbol-draft-1.png](logo-drafts/symbol-draft-1.png). Don't use as is.

- It reads as a generic "file" icon, the same one every operating system already has, so nobody would recognise it as Sentio. That is the opposite of what makes Apple's symbol work.
- The notch at the foot looks like a door or a charging port, not a citation.
- **Next direction:** build the symbol from the wordmark's own O (the rounded rectangle), filled solid, with a single cut that reads as a page corner or a citation mark. The symbol and the wordmark then share one shape language, as in the strongest brand systems.

### Symbol, round 2: [symbol-draft-2.png](logo-drafts/symbol-draft-2.png). Right idea, needs a redraw.

- **Made with:** Figma's image tool. The first attempt failed on Figma's side (debug ID `917d1804-0b25-4386-8bac-b0927d21cd90`); the retry worked.
- **What works:** it's built from the wordmark's O, as one solid shape with one cut, so the symbol and wordmark now share a shape language. It is simple enough to work at 16px.
- **What to fix in Figma, by hand:**
  - **Bigger cut.** It's too small to read as a turned page corner; at small sizes it looks like a SIM card or a chat bubble. Make the cut about 30–35% of the shape's height.
  - **Matching corners.** The corners are much rounder than the wordmark's O. Use the O's exact radius.
  - **Clean join.** Where the cut meets the right-hand side there's a small curved bump left over. The cut should meet the side in one straight, crisp line.
- **Next step:** stop generating. Draw the final symbol and wordmark as vectors in the Figma file, on one grid with one stroke width and one corner radius, then export SVGs for the app.
