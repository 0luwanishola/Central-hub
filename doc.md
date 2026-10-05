# Central Hub UI/UX Recommendations

## Review scope

This is a code-based review of the React frontend, including the dashboard, navigation, tool catalog, activities, notes, settings, and Code Quest. I reviewed the linked [UI UX Pro Max skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/main/.claude/skills/ui-ux-pro-max/SKILL.md) and its [UX quick reference](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/blob/main/.claude/skills/ui-ux-pro-max/references/quick-reference.md). The recommendations apply its priorities around accessibility, touch and keyboard interaction, responsive layouts, readable text, consistent visual styles, and useful feedback.

This review did not include rendered screenshots, browser testing, or assistive-technology testing. The contrast figures below are calculated from the current CSS color tokens and should be confirmed with an accessibility checker during implementation.

## Overall direction

Keep Central Hub's restrained teal and neutral look. The four dashboard destinations, separate offline activities, browser-saved notes, and Python/SQL learning give the product a clear purpose. The best next step is to make those destinations easier to find and more comfortable to use across screen sizes, rather than adding more decoration.

## Highest-priority improvements

### 1. Make mobile navigation fully operable

In [AppShell](frontend/src/app/AppShell.tsx), the mobile menu opens visually, but the toggle has no `aria-expanded` state, there is no Escape-key close behavior, and focus is not returned to the menu button after closing. In [styles.css](frontend/src/styles.css), the closed sidebar moves off-screen with a transform; that alone does not remove its links from keyboard tab order. The mobile menu button is 34px tall and the theme button is 37px tall.

**Recommendation:** expose the open state with `aria-expanded` and `aria-controls`; close on Escape; move focus into the menu when opened and return it to the trigger when closed. Make the closed drawer inert and hidden from assistive technology. Add a skip link to the main content and move focus to the page heading after route changes. Aim for 44px touch targets for the mobile controls.

### 2. Improve small text and light-theme contrast

The stylesheet uses 8–11px for many useful labels and descriptions, including feature-card copy, tool details, Code Quest hints, table text, and sports fixture labels. On mobile, this makes common information harder to read. The `--muted` token is `#768292`; its contrast is about **3.90:1 on white** and **3.64:1 on the page background**, below the skill's 4.5:1 target for normal text. The dark-theme muted text has better contrast against its current surfaces.

**Recommendation:** establish a type scale, use at least 16px for mobile body copy, and keep compact metadata at 12px or larger where it remains readable. Darken the light-theme muted token, then verify every text/background pair in both themes. Keep line height around 1.5 and allow text to wrap instead of shrinking or clipping it.

### 3. Add clear keyboard focus and complete the tab behavior

The stylesheet removes the browser outline from the tool search and the LiveScore date input, but those controls do not define a replacement focus style. Activities and Code Quest use `role="tablist"` and `role="tab"` on buttons, while selection currently relies on ordinary Tab navigation; the expected arrow-key movement for tabs is not implemented.

**Recommendation:** add a consistent, high-contrast `:focus-visible` ring to links, buttons, and inputs, including a `:focus-within` state on the search field. For the activity and track selectors, either implement arrow/Home/End navigation with roving focus or use a labelled button group instead of tab semantics. Confirm focus remains visible below the sticky top bar and after navigation.

## Next improvements

### 4. Make the home page a faster starting point

The dashboard in [CatalogPage](frontend/src/features/catalog/CatalogPage.tsx) has four equal feature cards and then shows the first four ready tools returned by the backend. The search field appears only after opening Digital tools, and the current quick tools are selected by list order rather than the person's usage.

**Recommendation:** add a compact, prominent search on the home page that searches tools and destinations. Make the quick-tool area configurable through recently used or pinned tools, and include a clear “Continue Code Quest” action when progress exists. Keep the four main destinations; this makes the hub's multifunction purpose clearer without adding more top-level sections.

### 5. Make tool discovery and filters easier on phones

The tool catalog's category pills are links, but their active visual style has no matching `aria-current` state. At the mobile breakpoint, the pills become a horizontally scrolling, non-wrapping row with no visible indication that more categories are off-screen. Search text and filter state are held locally in the page, so they can be lost when navigating away and back.

**Recommendation:** expose the selected collection semantically, wrap category options on small screens or provide a labelled select, and preserve the current search/filter state in the URL. Add a visible clear-search action and a result count so users can recover quickly from an empty result.

### 6. Help Code Quest learners keep their place

The guided editor in [LearnPage](frontend/src/features/learning/LearnPage.tsx) now provides starter code, hints, output, and progressive levels. Changing the track or level resets the editor to its starter code, so an unfinished attempt can be lost. The task, hint count, and supporting explanation also use small text sizes.

**Recommendation:** save drafts per learner, language, and level (in browser storage) and restore them when returning to a challenge. Make run, error, success, and output states easy to distinguish without relying on color alone. Keep the current staged hints, but give the editor comfortable height on mobile and ensure its task, help, and output remain readable at browser zoom.

### 7. Improve game and utility feedback for screen readers

The activities in [ActivitiesPage](frontend/src/features/activities/ActivitiesPage.tsx) already announce game status, and the tic-tac-toe squares have row and column labels. Hidden Memory Match cards all have the same accessible name (“Hidden card”), so their positions are difficult to distinguish. In [NotesPage](frontend/src/features/notes/NotesPage.tsx), Clear note immediately removes the saved text without an undo path. Some utility outputs in [ClientUtility](frontend/src/features/tools/ClientUtility.tsx) have a visible output heading that is not programmatically associated with the read-only output field.

**Recommendation:** label hidden cards by position and announce match/move updates. Give destructive clear actions a brief Undo option. Associate output headings with their result fields and announce copy success through a polite live region.

### 8. Use one icon and spacing system

Navigation and feature cards use a mixture of text glyphs, emoji, and tool icons supplied by the backend. The linked skill recommends one consistent vector icon style and clear accessible treatment for decorative versus meaningful icons. Spacing, corner radii, and text sizes also vary in small increments throughout the single large stylesheet.

**Recommendation:** choose one lightweight SVG icon set or a small inline SVG library, define icon sizes, and mark decorative icons as hidden from assistive technology. Centralize type, spacing, radius, focus, and elevation values as design tokens. Keep semantic labels and text with icons, especially for tool status and game state.

## Suggested implementation order

1. Fix mobile drawer focus/keyboard behavior and add a skip link.
2. Raise small text sizes, improve muted light-theme contrast, and establish visible focus styles.
3. Make the home search and quick-tool selection useful for repeat visits.
4. Improve category filtering, Code Quest draft recovery, and game/output announcements.
5. Consolidate icons and CSS tokens as those screens are touched.

## Review checklist

- Check the dashboard and key flows at 375, 768, 1024, and 1440px widths, plus 200% zoom.
- Complete navigation, tool search, a memory game, and a Code Quest challenge using only a keyboard.
- Verify light and dark text, control borders, focus rings, success, and error states for contrast.
- Confirm labels, active navigation, tab/group controls, results, and status announcements with a screen reader.
- Check that the page itself does not scroll horizontally; any internal table or code overflow should be deliberate and usable.
- Preserve the existing `prefers-reduced-motion` behavior while keeping interaction feedback responsive.
