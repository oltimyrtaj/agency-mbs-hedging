# 2025 presentation templates: reuse notes

Reference notes for building the new executive summary, slide deck, and talk script in the visual identity of Olti Myrtaj's Fall 2025 Erdős Institute project ("Hedging a U.S. Treasury Bond Portfolio and Modeling Interest Rate Risk"). All values below were measured from the files (OOXML parts, python-pptx and python-docx run data, PDF word boxes, and 96 dpi renders). Values that could not be determined are marked as such.

**The statistics in the 2025 files (volatility, variance reduction, VaR, DV01 values, and every other number) describe the 2025 Treasury project only. They are not targets, benchmarks, or expectations for the new project.**

Byte-identical copies of the five templates live in `communication/templates_2025/`.

---

## 1. Sources

Paths are relative to the folder "erdos quant project 2" on the author's computer.

| File | Relative path | Bytes | SHA-256 | Pages or slides |
|---|---|---|---|---|
| Slide deck | `erdos quant project 2025/bonds_project/hedging_bonds_slides.pptx` | 643,570 | `5a5ceb75b08704e5d00507eaa8450881ef4ec97e9d7b73b618f613c0662d0d6f` | 11 slides, 11 notes pages |
| Slide deck PDF | `erdos quant project 2025/bonds_project/hedging_bonds_slides.pdf` | 364,094 | `46edf8d2cf5586f8fae4e49d21860e14997c00f5c0a60d99e34559e6ad7f9d97` | 11 pages, 960 × 540 pt |
| Executive summary | `erdos quant project 2025/bonds_project/hedging_bonds_executive_summary.docx` | 59,984 | `99d9984436dbbf748fc094ffa200f8f42a25aaff23512ccd09415d89bdb210c4` | 3 pages when rendered (metadata says 1, stale) |
| Executive summary PDF | `erdos quant project 2025/bonds_project/hedging_bonds_executive_summary.pdf` | 172,416 | `b2a9bf72fb09c34457796860a81a9a464168e000a00f4e7c5e38927c001c6a96` | 3 pages, US Letter |
| Talk script | `erdos quant project 2025/bonds_project/Treasury_Bonds_Hedging_Presentation_Script.docx` | 31,593 | `a230f78816ebe6528580601ab964c32c300ce15cc0dbe93d6c85e2235091f661` | 3 pages |

- Copy check: all five copies in `communication/templates_2025/` have the same SHA-256 as the sources and pass a byte-wise `cmp` (5 of 5 identical).
- Duplicates: `erdos quant project 2025/916c21_81219d4f05104d3aa82b78ec54d5071e.pdf` is byte-identical to the slide PDF, and `erdos quant project 2025/916c21_d944ccd7d5404cffb4b57c08d8ab6f03.pdf` is byte-identical to the summary PDF.
- Dates (file metadata): deck created 2025-09-22 and last saved 2025-11-07 in PowerPoint for Mac 16. Both PDFs were exported 2025-11-06 (PST). The summary .docx was last saved 2026-01-26, after its PDF, and differs from the PDF by one word (section 5). The script .docx was last saved 2025-11-07.

---

## 2. Slide deck (`hedging_bonds_slides.pptx`)

### 2.1 Page setup, theme, master, and background

| Property | Value |
|---|---|
| Slide size | 12,192,000 × 6,858,000 EMU = 13.333 × 7.500 in, 16:9 ("Widescreen") |
| Notes page size | 6,858,000 × 9,144,000 EMU = 7.5 × 10 in |
| Theme | "Office Theme" (the Office 2023+ default), one slide master |
| Font scheme | "Office": major (headings) **Aptos Display**, minor (body) **Aptos** |
| Color scheme | "Office", see table below |
| Layouts used | "Title Slide" (slide 1) and "Title and Content" (slides 2 to 11). The other 9 layouts of the master are unused |
| Background | Master background `bg1` = white #FFFFFF. No slide overrides it. No background images, gradients, or master graphics |
| Transitions, animations, and hyperlinks | None on any slide |
| Native charts | None (no chart parts in the package) |

Theme color scheme:

| Slot | Hex | Use in this deck |
|---|---|---|
| dk1 | #000000 | All titles and body text |
| lt1 | #FFFFFF | Background and the text on teal and grey shapes |
| dk2 | #0E2841 | Unused on slides |
| lt2 | #E8E8E8 | Unused |
| accent1 | #156082 | Main brand color: callout bars, table header rows, process boxes, and arrows |
| accent2 | #E97132 | Unused on slides |
| accent3 | #196B24 | Unused |
| accent4 | #0F9ED5 | Unused |
| accent5 | #A02B93 | Unused |
| accent6 | #4EA72E | Unused |
| hlink | #467886 | Unused |
| folHlink | #96607D | Unused |

Derived colors actually rendered (sampled from the renders):

| Color | Definition | Where |
|---|---|---|
| #156082 | accent1 | Callout bars (slides 2, 3, 5, 7, and 11), teal box on slide 9, table header rows, first table column on slides 8 and 11, SmartArt step boxes, block arrows, and connector bars |
| #D9D9D9 | bg1 at 85% luminance | Body rows of all boxes and data cells of all tables |
| #7F7F7F | bg1 at 50% luminance | Callout bars on slides 4 and 6 |
| #AAB6C1 | accent1 at 60% tint | SmartArt connector arrows (slides 4, 8, and 10) |
| #000000 | tx1 | 1 pt outer and header borders on the slide 8 and 11 tables |

### 2.2 Typography as used (run level)

Fonts embedded in the PDF export: AptosDisplay-Bold, Aptos, Aptos-Bold, ArialMT (the "•" bullet glyph), CambriaMath (equations), and CourierNewPSMT (the "o" sub-bullet glyph). Font sizes were confirmed against PDF word-box heights.

| Element | Font | Size | Weight | Color | Alignment |
|---|---|---|---|---|---|
| Content-slide title (line 1 of the title placeholder) | Aptos Display | 54 pt | Bold | Black | Left, with the placeholder anchored middle and 90% line spacing |
| Subtitle sentence (line 2 of the same placeholder, after a line break) | Aptos Display | 22 pt (24 pt on slide 9, 24 pt and 22 pt mixed on slide 7) | Bold | Black | Left |
| Title-slide title | Aptos Display | 60 pt in the layout, shown at 54 pt by autofit (90% font scale) | Bold | Black | Centered and bottom-anchored |
| Title-slide subtitle banner | Aptos | 20 pt | Regular | White on #156082 | Centered |
| Title-slide name | Aptos | 40 pt | Bold | Black | Centered |
| Title-slide affiliation, course, and date lines | Aptos | 18 pt | Regular | Black | Centered |
| Title-slide email | Aptos | 18 pt | Bold | Black | Centered on the slide |
| Author tag, top right of slides 2 to 11 | Aptos | 10 pt | Regular | Black | Right |
| Body bullets (slide 2 body placeholder) | Aptos | 18 pt level 1, 14 pt level 2 | Regular with bold key terms | Black | Left with "•" Arial bullets |
| Lead sentence above content (slide 7) | Aptos | 20 pt | Regular with bold key phrase | Black | Centered |
| Box header row | Aptos | 18 pt | Bold | White on #156082 | Centered |
| Box body row | Aptos | 18 pt | Regular with bold lead-in terms | Black on #D9D9D9 | Left with "•" Arial bullets at a 0.3125 in hanging indent and "o" Courier New sub-bullets at 0.8125 in |
| Callout bar | Aptos | 20 pt | Regular with bold lead-in (slides 2 to 5) | White on #156082 or #7F7F7F | Centered and anchored middle |
| SmartArt step box | Aptos | 16 pt heading + 12 pt bullets (slides 4 and 8), 17 pt + 13 pt (slide 10) | Heading bold, bullets regular (bold on slide 8) | White on #156082 | Left |
| Data tables (slides 8 and 11) | Aptos | 18 pt | Header row and first column bold | White on #156082 for headers, black on #D9D9D9 for data | Centered horizontally and vertically |
| Figure captions | Aptos | 18 pt centered with bold phrases (slide 8), 14 pt left-aligned (slide 10) | Regular | Black | As stated |
| Equations | Cambria Math (Office Math) | Matches surrounding text | Regular | Black or white | Inline |

### 2.3 Geometry of recurring elements

Positions are left, top, width, and height in inches.

| Element | Left | Top | Width | Height | Notes |
|---|---|---|---|---|---|
| Title placeholder (slides 2 to 11) | 0.427 | 0.021 | 11.990 | 1.450 | Moved up and left from the master default (0.917, 0.399, 11.5, 1.45) |
| Rendered title glyphs (54 pt) | 0.53 | 0.07 | (varies) | 0.92 | Glyph box 0.07 to 0.99 in |
| Rendered subtitle glyphs (22 pt) | 0.53 | 0.96 | (varies) | 0.36 | Glyph box 0.96 to 1.32 in |
| Author tag (name over email) | 11.758 | 0.003 | 1.589 | 0.438 | Right edge 13.346 in, 0.013 in past the slide edge |
| Body placeholder (slide 2) | 0.427 | 1.471 | 6.856 | 3.815 | Only slide with a filled body placeholder |
| Content region (typical) | 0.26 | 1.34 | 12.95 | 4.7 | Between the subtitle and the callout bar |
| Callout bar | 0.118 | 6.029 (most common) | 13.098 | 1.008 | Top varies from 5.468 to 6.421 in by slide. Slide 2 uses height 1.450 |
| Two-column boxes (slides 3 and 5) | 1.001 and 6.912 | 1.471 or 1.938 | 5.421 each | 2.399 to 3.500 | 0.490 in gutter, 1.0 in outer margins |

Callout bars are rounded rectangles with the default corner radius (16.7% of the shorter side, about 0.17 in on a 1.008 in bar), no outline, and no shadow.

### 2.4 Recurring elements

- **Author tag**: "Olti Myrtaj" over his email address, 10 pt and right-aligned, in the top-right corner of slides 2 to 11.
- **Callout bar**: one full-width rounded rectangle near the bottom of slides 2 to 7 and 11 with a one- or two-sentence takeaway in 20 pt white. Teal on slides 2, 3, 5, 7, and 11, grey on slides 4 and 6. Slide 9 uses a teal rounded box on the right in its place. Slides 1, 8, 9, and 10 have no bottom bar.
- **Header box**: a one-column, two-row table with a teal header row and a #D9D9D9 body row holding bullets (slides 3, 5, 6, 7, and 9).
- **Connectors**: teal rectangles and a teal down arrow join boxes (slide 3 "merge" connector, slide 6 three-to-one connector). Slide 9 uses a teal right arrow.
- **Not present**: slide numbers, footers, dates, logos, decorative accent bars or rules, and a closing or questions slide.

### 2.5 Figures

All charts are pasted PNG images saved by matplotlib 3.1.3 at 72 dpi, except slide 7, which is a screenshot (EXIF "Screenshot"). Every image keeps its native aspect ratio (no stretching or cropping) and has no border or shadow. Chart titles are inside the images. The deck places figures in the right half of the slide with text or a process diagram on the left (slides 4, 7, and 10), or below a process diagram (slide 8).

| Slide | Content | Pixels | Displayed size (in) | Left, top (in) | Effective px/in | Series colors |
|---|---|---|---|---|---|---|
| 4 | Interpolated yield curve (line) | 538 × 337 | 5.360 × 3.358 | 6.880, 1.340 | 100 | #1F77B4 (matplotlib default blue) |
| 7 | ETF betas by key rate (bars) | 884 × 716 | 5.269 × 4.267 | 7.935, 1.908 | 168 | #3B75AF blue and #EF8636 orange |
| 8 | Backtest cumulative P&L (lines) | 712 × 280 | 7.069 × 2.780 | 0.264, 3.750 | 101 | #1F77B4 blue and #FF7F0E orange |
| 10 | Simulated 10-year yield paths (lines) | 712 × 280 | 5.944 × 2.338 | 6.622, 1.296 | 120 | Default color cycle at partial opacity |
| 10 | Variance-reduction histogram | 496 × 297 | 4.531 × 2.713 | 7.413, 4.197 | 109 | #6CAD89 green bars and a dashed black median line |

The chart font cannot be read from the raster images. It is visibly different from Aptos (matplotlib default style). No chart uses the deck's teal.

### 2.6 Tables

- Every table references the style "Medium Style 2 – Accent 1" (`{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}`) with header row and banded rows switched on. The file also stores "Medium Style 2 – Accent 4", which no table uses.
- Header row: #156082 fill, 18 pt bold white Aptos (from the style), 1 pt white inner borders, and a 3 pt white line under the header row.
- Body cells: explicitly filled #D9D9D9, which overrides the style's banded tints.
- Data tables (slides 8 and 11): first column manually filled #156082 with bold white labels, top-left cell unfilled (empty on slide 8, a black bold table label on slide 11), 1 pt black borders added on the outer edges and around header and first-column cells, and all text centered horizontally and vertically.
- Header boxes (slides 3, 5, 6, 7, and 9) are the same table style with one column and left-aligned bullets in the body row.

### 2.7 Process diagrams (SmartArt)

| Slide | SmartArt layout (ID) | Frame (left, top, width, and height in inches) | Steps | Step box size (in) |
|---|---|---|---|---|
| 4 | `layout/process2` (Vertical Process) | 0.917, 1.378, 4.801, 4.651 | 3 | 3.732 × 1.163 |
| 8 | `layout/process1` (Basic Process) | 0.427, 1.670, 12.480, 1.747 | 4 | 2.398 × 1.702 |
| 10 | `layout/process2` (Vertical Process) | 0.000, 1.392, 5.900, 6.029 | 3 | 4.164 × 1.507 |

All three use the color variant `colors/accent1_2` (solid #156082 boxes and #AAB6C1 arrows) and the default quick style `quickstyle/simple1`. Step headings are numbered "1." to "4.", with one omission on slide 10.

### 2.8 Equations

Equations are native Office Math (Cambria Math) on slides 4 and 10 (inside SmartArt) and slide 7 (inside a table and a text box). PNG fallbacks for older viewers are stored as `image10`, `image20`, `image21`, `image40`, and `image60`.

### 2.9 Notes pages

Every slide has speaker notes (1,048 words in total) that repeat the talk script almost verbatim. The text was pasted from the script, so it carries 18 pt Cambria (slides 1 to 6 and 11) or 18 pt Times New Roman (slides 7 to 10) formatting. The notes master is the default (12 pt Aptos, slide image above notes). No notes page carries extra content.

### 2.10 Text density

On-slide words per slide from the PDF text (including the 3-word author tag and equation glyphs): 50, 157, 150, 110, 114, 105, 149, 99, 79, 128, and 64 for slides 1 to 11 (1,205 total).

---

## 3. Slide outline

| # | Title (subtitle sentence) | Content type | Message |
|---|---|---|---|
| 1 | Hedging a U.S. Treasury Bond Portfolio and Modeling Interest Rate Risk | Title slide: title, teal subtitle banner, name block, and email | Project, author, course, and date |
| 2 | Background and Overview (Bonds' sensitivity to interest rate risk = Need to hedge portfolios to retain value) | Text bullets left, arrow graphic right, and teal callout | Rates up means prices down, so hedge. States the objective |
| 3 | Data Acquisition and Preprocessing (Building the dataset we use to design the hedge) | Two-column header boxes, "merge" connector, and teal callout | FRED yields and yfinance ETF prices merged into one series |
| 4 | Bond Pricing (Interpolating the yield curve to price bonds based on changing interest rates) | Vertical 3-step process with equations, chart right, two bullets, and grey callout | The interpolated curve prices any bond |
| 5 | DV01s and KRDV01s (Metrics that measure sensitivity to interest rate changes) | Two-column header boxes and teal callout | DV01 gives the size of rate risk and KRDV01 its location |
| 6 | Toy Portfolio (Designing and analyzing the portfolio we will hedge) | Three-column box, connector, summary box, and grey callout | Three-bond portfolio and its rate exposure |
| 7 | Hedge Design (We neutralize interest rate risk with a key-rated hedging mechanism) | Lead sentence, text box with equations left, bar chart right, and teal callout | Regression betas and least squares give hedge weights |
| 8 | Applying Hedge to Real Data (Backtesting key-rated hedge on real data (2018-2025)) | Horizontal 4-step process, line chart with caption, and metrics table | The hedge lowers risk in a historical backtest |
| 9 | Beyond History (Simulating many plausible interest rate environments to validate hedging scheme) | Header box with limits, right arrow, and teal rounded box | One historical path is not enough, so simulate |
| 10 | Simulating Many Futures (Applying a Vasicek model with Monte Carlo simulations to stress-test hedge performance) | Vertical 3-step process left and two charts with captions right | Vasicek, PCA, and Monte Carlo stress test |
| 11 | Main Results (Hedge performance validated across historical and simulated data) | Two metrics tables and teal callout | The hedge holds in history and in simulation |

---

## 4. Reusable layouts

All positions are left, top, width, and height in inches. Every content slide also carries the title placeholder and author tag from section 2.3.

| Purpose | Template slide | Geometry |
|---|---|---|
| Title slide | 1 | Title 0.435, 0.948, 12.380 × 1.777 (54 pt bold, centered). Teal banner 1.667, 2.973, 10.000 × 0.864 (20 pt white). Name block 2.851, 4.527, 7.483 × 2.895 (40 pt bold name, then 18 pt lines). Email 5.250, 6.858, 2.835 × 0.707 (18 pt bold, move up about 0.1 in so it ends inside the slide) |
| Claim + figure | 7 (primary) | Subtitle states the claim. Lead sentence 0.427, 1.358, 12.179 × 0.438 (20 pt, centered). Header box left 0.272, 1.908, 7.204 × 3.925. Figure right 7.935, 1.908, 5.269 × 4.267. Callout bar 0.118, 6.362, 13.098 × 1.008 |
| Claim + figure with steps | 4 | Vertical process left 0.917, 1.378, 4.801 × 4.651. Figure right 6.880, 1.340, 5.360 × 3.358. Two 18 pt bullets below the figure at 6.880, 4.669 (width 5.739). Callout bar 0.118, 6.298, 13.098 × 1.008 |
| Two-column comparison | 5 (primary), 3 (with merge connector) | Header boxes at 1.001, 1.938 and 6.912, 1.938, each 5.421 × 2.399 (header row about 0.43 in, body row about 1.97 in). Callout bar 0.118, 5.468, 13.098 × 1.008. Slide 3 variant: boxes 5.421 × 3.500 at top 1.471, connector bar 5.591, 5.188, 2.151 × 0.285, down arrow 6.446, 5.407, 0.442 × 0.567, and callout bar at top 6.029 |
| Table | 11 (results), 6 (inputs) | Slide 11: tables 0.427, 1.588, 12.480 × 1.784 and 0.427, 3.610, 12.480 × 1.750, three 4.160 in columns, rows 0.36 to 0.50 in, and callout bar 0.118, 6.029, 13.098 × 1.008. Slide 6: three-column box 1.001, 1.471, 11.174 × 2.030 (3 × 3.725 in), connector, and full-width summary box 1.001, 4.516, 11.174 × 1.700 |
| Methods or pipeline | 8 (horizontal), 10 (vertical) | Slide 8: Basic Process frame 0.427, 1.670, 12.480 × 1.747 with 4 steps of 2.398 × 1.702 at a 3.357 in pitch and arrows of 0.508 × 0.595. Lower area: figure 0.264, 3.750, 7.069 × 2.780, caption 0.523, 6.483, 6.553 × 0.707, and table 8.055, 3.615, 4.852 × 3.622. Slide 10: Vertical Process frame 0.000, 1.392, 5.900 × 6.029 with figures and 14 pt captions on the right |
| Takeaways | 2 (bulleted), 11 (results) | The deck has no dedicated takeaways slide. Slide 2 offers the only bulleted body placeholder (0.427, 1.471, 6.856 × 3.815, 18 pt and 14 pt) plus a callout bar 0.118, 5.526, 13.098 × 1.450. Slide 11 ends the deck with results tables and a one-sentence callout |
| Limitations | 9 | Header box 0.427, 2.239, 5.615 × 3.403 listing limits, right arrow 6.169, 3.596, 1.972 × 1.126, and teal rounded box 8.263, 3.305, 5.002 × 1.709 (20 pt white). Pull the box in to a 0.118 in right margin |

---

## 5. Executive summary (`hedging_bonds_executive_summary.docx` and `.pdf`)

| Property | Value |
|---|---|
| Page | US Letter 8.5 × 11 in, portrait, one section, and one column |
| Margins | 1.0 in on all sides, header and footer distance 0.5 in |
| Header and footer | Empty. No page numbers |
| Font | Times New Roman throughout (document default 12 pt). The document theme is the Office 2023+ theme (Aptos), which the text does not use |
| Title block | Centered, 1.15 line spacing, and 0 pt before and after: title 15 pt bold, course line 12 pt, a blank line, author 14 pt bold, email 12 pt, and a blank line |
| Body | 12 pt, single line spacing, left-aligned (ragged right), 0 pt before and after, no first-line indent, and paragraph style "Normal (Web)" |
| Section headings | 14 pt bold black, made with the "Strong" character style plus a 14 pt size on a "Normal (Web)" paragraph. No Word heading style is applied (Heading 1 to 3 exist but are unused). Space before headings comes from an empty paragraph (first three headings) or Word's automatic spacing (later headings), 0 pt after |
| Inline emphasis | "Emphasis" (italic) and "Strong" (bold) character styles inside sentences |
| Word count | 975 words in all text (title block 24, headings 26, caption 14, table titles 6, table cells 30) and 875 words of prose. Word's stored count is 973 |
| Page count | 3 (Word PDF and a LibreOffice render agree). Page 3 is about half full (text ends 5.70 in from the top). The stored metadata says 1 page and is stale |

Section order (headings verbatim) with prose word counts:

1. Title block: title, "Final Project: Erdos Institute Fall 2025 Quantitative Methods in Finance", name, and email
2. Untitled overview paragraph (104 words): problem, approach, and evaluation in one paragraph
3. Data Acquisition and Preprocessing (86)
4. Pricing and Risk (Bond Analytics) (121)
5. Toy Portfolio (55)
6. Hedge Design (142)
7. Applying the Hedge on Real Data (88), followed by Figure 1
8. Simulating Futures (Stress Testing) (120)
9. Main Results (91), followed by two tables
10. Conclusion (68)

There is no limitations section.

Figures and tables:

- **Figure 1** (the only figure): inline PNG at 6.500 × 2.556 in (full text width), the same 712 × 280 px file as slide 8 (110 px/in at this size). Caption below it in Word's "Caption" style with a SEQ Figure field ("Figure 1: ..."), 9 pt, italic switched off, color #0E2841, and centered.
- **Two tables**, style "Table Grid" (single 0.5 pt black borders, no shading), centered on the page, three columns of 2.164 to 2.165 in (6.494 in total), four rows (header plus three metrics), a bold header row, and all cells left-aligned in 12 pt Times New Roman. Each table has a bold 12 pt centered title paragraph above it ("Historical Backtest Results", "Simulated Data Results"). These titles are plain paragraphs without Word caption numbering.

PDF and .docx differ by one word: the PDF reads "for the remained of this document" and the .docx reads "for the remainder of this document".

---

## 6. Presentation script (`Treasury_Bonds_Hedging_Presentation_Script.docx`)

| Property | Value |
|---|---|
| Page | US Letter, margins 1.25 in left and right and 1.0 in top and bottom, no header or footer, and 3 pages |
| Origin | Created from python-docx's default template (core properties creator "python-docx"), then edited in Word |
| Structure | 11 sections, one per slide, each a "Heading 2" title followed by 1 to 5 prose paragraphs |
| Headings | Calibri 13 pt bold #4F81BD (2013 Office theme of the python-docx template) |
| Body | Mixed: "Normal" (Cambria 11 pt, 10 pt after, 1.15 line spacing) and "Normal (Web)" (Times New Roman 12 pt). Manual line breaks add extra gaps |
| Not present | Title, author line, slide numbers, timing marks, and speaker cues such as [click], [pause], or [next slide] |
| Voice | First person and conversational ("Hi, I'm Olti Myrtaj."). Transitions are spoken ("Now, before we do any hedging", "So next"). Visuals are referenced in the text ("As the figure shows", "We see in the bottom right") |
| Words | 1,049 spoken words plus 28 heading words. Word's stored count is 982 |
| Speaking time at 140 wpm | 7.5 min (7 min 30 s) |

Section-to-slide mapping with estimated time at 140 words per minute:

| Slide | Script heading | Words | Time |
|---|---|---|---|
| 1 | Opening | 35 | 15 s |
| 2 | Background and Objective | 84 | 36 s |
| 3 | Data & Preprocessing | 78 | 33 s |
| 4 | Bond Pricing | 73 | 31 s |
| 5 | DV01 and Key-Rate DV01 | 73 | 31 s |
| 6 | Toy Portfolio | 62 | 27 s |
| 7 | Hedge Design | 152 | 65 s |
| 8 | Backtesting on Real Data | 162 | 69 s |
| 9 | Beyond History | 79 | 34 s |
| 10 | Simulating Many Futures | 170 | 73 s |
| 11 | Main Results | 81 | 35 s |

The average is 95 spoken words per slide. The deck's speaker notes contain the same text (1,048 words) with small wording differences.

---

## 7. How to reuse (checklist)

- [ ] Keep the 13.333 × 7.5 in (16:9) slide size. Start from a copy of `communication/templates_2025/hedging_bonds_slides.pptx`, or from a blank deck with the same Office theme, so the theme fonts (Aptos Display and Aptos) and colors carry over.
- [ ] Keep the white background and the color roles: #156082 for header rows, callout bars, process boxes, and arrows, #D9D9D9 for box bodies and table data cells, black text on white or grey, and white text on teal.
- [ ] Keep the title pattern: one title placeholder at 0.427, 0.021, 11.990 × 1.450 in holding a 54 pt bold title, a line break, and a 22 pt bold subtitle sentence that states the slide's message. Use 22 pt on every slide. End the 54 pt line before about x = 11.7 in so it clears the author tag. The 34-character slide 3 title ends at 11.81 in and touches the tag, so titles of about 32 characters or fewer are safe.
- [ ] Put the author tag (10 pt, right-aligned) in the top-right corner of every content slide.
- [ ] Use one callout bar per slide at a fixed position (0.118, 6.029, 13.098 × 1.008 in) with 20 pt white text and a bold lead-in. Use teal throughout, or give grey one stated purpose.
- [ ] Use header boxes for lists and the slide 8 and 11 table pattern for numbers, with 18 pt text.
- [ ] Keep the figure placement (text or process diagram on the left, figure about 5.3 to 6 in wide on the right) with native aspect ratio. Regenerate every chart at 300 dpi at its placed size, or as SVG, with one matplotlib style for all charts: the deck palette (#156082 first series, #E97132 second series, and #7F7F7F reference lines), one sans-serif font, and tick labels of at least 12 pt at placed size.
- [ ] Add slide numbers. They help a recorded video and any Q&A.
- [ ] Adapt the narrative and length to the new project. The Fall 2026 deliverables are an executive summary that briefly describes the problem, methodology, principal findings, and important limitations, plus a short video. Budget about 140 spoken words per minute of video. Confirm page and minute limits in the current Erdős Institute instructions (not reviewed in this task).
- [ ] Add a limitations slide (slide 9 pattern) and a "Limitations" section in the summary. The 2025 summary has none.
- [ ] For the summary, keep US Letter, 1.0 in margins, Times New Roman 12 pt body, a 15 pt bold centered title block, and 14 pt bold section headings, applied through real Word heading styles formatted to match. Order the sections as problem, methodology, principal findings, and limitations. Keep numbered figure captions and Table Grid tables.
- [ ] For the script, use one Heading 2 section per slide named with the exact slide title, one body font, a time mark per section at 140 wpm, and a cue for each slide change.
- [ ] Treat every 2025 number in these files as specific to the 2025 Treasury project. None of them is a target, benchmark, or expectation for the new project.

---

## 8. Problems to avoid

Slide deck:

1. Callout bars move between slides (top edge from 5.468 to 6.421 in), and their fill alternates between teal (slides 2, 3, 5, 7, and 11) and grey (slides 4 and 6) with no stated rule.
2. Subtitle size varies: 22 pt on most slides, 24 pt on slide 9, and 24 pt and 22 pt within one sentence on slide 7.
3. SmartArt text sizes differ (16 pt and 12 pt on slides 4 and 8, 17 pt and 13 pt on slide 10), bullet weight differs (bold on slide 8, regular elsewhere), and slide 10's first step lacks its "1." number.
4. Caption styles differ: 18 pt centered with bold phrases on slide 8, 14 pt left-aligned on slide 10, and no captions on slides 4 and 7.
5. Figures are low resolution: 72 dpi matplotlib exports shown at 100 to 120 px/in on slides 4, 8, and 10, below the 144 px/in of a 1920 × 1080 video frame. Slide 7's chart is a screenshot. Summary Figure 1 reuses a 712 × 280 px image at 6.5 in wide (110 px/in).
6. Chart styling does not match the deck: matplotlib default fonts and colors, a green histogram, and a screenshot on slide 7. No chart uses the theme teal, and the axis labels are small and faint relative to 18 pt slide text (slide 10 top chart especially).
7. Empty "Content Placeholder 2" boxes remain on slides 3 to 7 and 9 to 11. They show prompt text in editing view and capture clicks. Slide 9's extends below the slide (bottom at 8.029 in).
8. Shapes extend past the slide: a slide 4 text box reaches 8.484 in (its box also overlaps the grey callout bar area), the slide 1 email box reaches 7.565 in, and the author tag reaches 13.346 in on slides 2 to 11.
9. Bottom margins are tight: slide 10's last process box ends 0.08 in above the bottom edge, and the callout bars on slides 6 and 7 end at 7.429 and 7.370 in.
10. The title placeholder (right edge 12.417 in) overlaps the author tag box (left edge 11.758 in). On slide 3 the 34-character title ends 0.075 in from the email text.
11. Slide 9's teal box ends 0.068 in from the right edge (callout bars keep 0.118 in), and the slide's lower third is empty.
12. Slide 6's portfolio summary box centers bulleted paragraphs, so bullets float mid-line.
13. The title-slide title depends on autofit (60 pt shrunk to 54 pt). A longer title would shrink further. Set 54 pt explicitly.
14. Alternative text is auto-generated and wrong ("A graph of numbers and squares..." on slide 7, "A graph showing the fall of the stock market" on summary Figure 1) or missing on the other images.
15. Speaker notes keep 18 pt Cambria and Times New Roman formatting pasted from the script.

Wording and content (all three files):

16. "Key-rated hedge" appears on slides 7, 8, and 10, in the summary, and in the script, alongside "key-rate hedge". The established term is "key-rate" (as in key-rate duration and KRDV01).
17. Slide 8 says "least-squared problem". The established term is "least-squares".
18. Slide 6 shows DV01 values as negative and KRDV01 values as positive for the same exposure. Use one sign convention.
19. Slide 7's callout says to "buy" IEF and TLT units while slide 8 says "Short ETF positions to hedge". Keep the hedge direction consistent.
20. "Erdos" is spelled without the "ő" in all three documents.
21. Typos: "The goal of this project to take" (script and slide 2 notes), "EF tracks" for "IEF tracks" (script), "remainer" (summary, Simulating Futures section), and "remained" (summary PDF only).
22. Spoken summaries ("roughly halves volatility", VaR "roughly cut in half") understate the changes shown in the slide 8 and 11 tables. Keep spoken numbers consistent with on-screen numbers.

Executive summary and script:

23. The summary .docx was edited after its PDF was exported, so the two files are out of sync by one word. Export the final PDF from the final .docx.
24. The summary has no limitations section, which the Fall 2026 requirements call for.
25. Summary headings are formatted runs inside "Normal (Web)" paragraphs, so Word shows no document outline, and spacing before headings is produced two different ways.
26. Summary tables left-align numbers and use plain bold paragraphs as titles. The figure caption is 9 pt navy, smaller than the 12 pt body.
27. The script mixes Cambria 11 pt and Times New Roman 12 pt body text, uses manual line breaks for spacing, and carries the Calibri and Cambria theme of the python-docx template, which differs from the deck's Aptos.
