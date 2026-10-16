# Design System

Desktop Qt Widgets app. Plain and calm: the web page being collected is the visual focus; the app's own
chrome stays quiet.

## 1. Design Direction

Style: Minimal, utilitarian
Mood: Calm, trustworthy, obvious
Design Principles:
- One primary action per screen
- Plain language, no jargon (no "selector", "HTTP", "DOM" in the main UI)
- Always show what the app is doing and why it stopped

## 2. Brand

Brand Name: Gleaner
Logo: Text wordmark only in MVP
Brand Voice: Short, direct, helpful. "Collected 120 records." not "Successfully completed extraction."

## 3. Color Palette

Primary: #1F4E78 (buttons, highlights, Excel header - matches existing export)
Secondary: #2E86C1
Background: #F7F8FA
Surface: #FFFFFF
Text: #1B1F24
Muted Text: #5F6B7A
Border: #D6DBE1
Success: #1E8449
Warning: #B9770E
Error: #C0392B
Pick highlight (in page): outline #F39C12 2px, fill rgba(243,156,18,0.15)
Hover outline (in page): #2E86C1 2px dashed

## 4. Typography

Font Family: Segoe UI (Windows system font)
H1: 16pt / Semibold (view titles)
H2: 12pt / Semibold (panel titles)
Body: 10pt / Regular
Small: 9pt / Regular (status bar, hints)

## 5. Spacing

Base Unit: 4px
Spacing Scale: 4 / 8 / 12 / 16 / 24 / 32
Panel padding 12px; gap between controls 8px.

## 6. Border Radius

Small: 3px (inputs)  Medium: 4px (buttons)  Large: 6px (cards/banners)

## 7. Shadows

None (flat Fusion style). Separation by borders.

## 8. Buttons

Primary Button: Primary fill, white text, one per view (Save, Run, Start)
Secondary Button: White fill, Primary border/text
Danger Button: Error fill, white text (Delete, Stop)
Disabled: 40% opacity, no hover
Loading: Text changes to the action in progress ("Opening...") and button disabled

## 9. Inputs

Default: 1px Border, Surface fill
Focus: 2px Secondary border
Error: 1px Error border + error text below in Small
Disabled: Background fill
Placeholder: Muted Text, example values ("e.g. https://www.example.com/doctors")

## 10. Cards / Banners

Banners for run outcomes: 12px padding, Large radius, left 4px stripe in Success/Warning/Error colour,
title in Body Semibold, details collapsible.

## 10a. Look (v0.8)

Minimal, flat, roomy. Content sits on Surface cards (1px Border, 10px radius) over the Background.
Inputs and buttons: 6px radius. Buttons come in four kinds: primary (filled, one per area: Open, Auto-detect,
Save recipe, New recipe, Run, Start), default (outlined), quiet (text only, for secondary actions such as
Pick again, Remove, Import) and link (How does this work?). Rarely used actions go in a "More" menu.
Steps are underline tabs. Tables have no grid lines, 36-40px rows, Muted headers. Thin scrollbars.
Prefer hiding a control that can't be used yet over showing it disabled, when hiding doesn't shift the
layout the user is working in. Font: Segoe UI Variable Text (Windows 11), Segoe UI otherwise.

## 11. Navigation

Header: none (native title bar).
Sidebar: left column, Surface background, 1px Border on the right. Top: menu button (collapse to 52 px,
icons only, names as tooltips; Ctrl+B). Middle: Library, Recipe builder, Run, Guide, Settings with icons;
selected item uses Primary text and icon + Selected fill. Bottom: theme button (icon + "Theme: <name>",
cycles Match Windows / Light / Dark; Ctrl+Shift+T).
Mobile Navigation: not applicable.

## 12. States

Loading: spinner/indeterminate progress + text of what is happening.
Empty: one sentence explaining what to do next + the primary button.
Error: Error banner, plain cause, what to do next; technical details collapsed.
Success: Success banner with next actions (Open Excel, Open folder).
Disabled: as Buttons/Inputs.

## 13. Icons

Icon Library: Windows icon font (Segoe Fluent Icons, falling back to Segoe MDL2 Assets), drawn in theme
colours by `app/widgets.py glyph_icon()`; redrawn when the theme changes.
Default Size: 20px in the sidebar
Icon Style: outline, Muted colour; Primary when selected

## 14. Responsive Design

Minimum window 1100 x 700. Builder splitter: browser 65% / panel 35%, user-resizable; preview table
docks at the bottom (collapsible). High-DPI scaling on.

## 15. Accessibility

- Keyboard: every action reachable by Tab; Esc cancels pick mode.
- Contrast: text meets WCAG AA on Background/Surface.
- Visible focus states.
- Accessible names on all buttons (setAccessibleName).
- Status never shown by colour alone (banners always have text; badges have labels).

## 16. Themes

Theme setting: Match Windows (default), Light, Dark. Match Windows follows Windows' app mode live (Qt 6.8+
also switches the title bar). Colour values live in `app/style.py` (LIGHT, DARK); widgets use roles, never
hard-coded colours (`style.color("ERROR")`).

Dark palette:
Primary: #5DA9E9 (text on primary buttons: #0F1418)
Secondary: #5DADE2
Background: #15191E
Surface: #1E242B
Text: #E6EAEF
Muted Text: #9AA5B1
Border: #323C47
Selected: #23384A
Success: #3FBF7F
Warning: #E0A63A
Error: #E5675A

The website shown in the builder's browser is never re-coloured.
