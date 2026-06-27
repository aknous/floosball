---
description: Add a release entry to the frontend changelog and bump the footer version, following the house format and rules
argument-hint: [optional — the version to cut, e.g. "v0.21.0", or leave blank to pick the next sensible bump]
---

Cut a changelog entry for the current release: $ARGUMENTS

The changelog lives in the **frontend** repo at `../floosball-react/src/data/changelog.ts` as the `CHANGELOG` array (newest first). The footer reads `CHANGELOG[0].version`, so adding a new top entry **auto-bumps the displayed version** — there is no separate version file to edit.

## What goes in the entry

Cover only what is **new in this release** — the delta that is shipping now and is not already in an earlier changelog entry. The cleanest way to scope it is the merge delta (e.g. `git log <prev-release>..HEAD --oneline` in both repos), then read the existing entries so you don't repeat anything already documented.

Group items into up to three sections, in this order, each optional:
- **New Features** — user-facing additions.
- **Changes** — adjustments to existing behavior, balance, or copy.
- **Fixes** — see the rule below.

Every item is a string prefixed with a `[Category]` tag (e.g. `[Facilities]`, `[Showcase]`, `[Sim]`, `[Front Office]`, `[Cards]`, `[Prognostications]`, `[Economy]`). Match the categories already used in the file.

## The Fixes rule (important)

**Fixes lists production bugs only.** Do NOT list fixes to features or changes that were built *during this same update*. While developing a new feature you will tune, refine, and fix it many times — none of that belongs in the changelog. Only a bug that existed in the live product and is now fixed counts as a Fix. If a "fix" is really just finishing a feature this update introduced, fold it into the New Features / Changes line for that feature instead.

## Writing rules

- **No em-dashes anywhere.** Use periods, commas, or "and". (Same rule as all user-facing copy.)
- **Keep it simple. Do not over-explain.** One or two plain sentences per item. State what changed from the player's point of view, not how it works under the hood. Avoid internal names, constants, and mechanics the player never sees.
- Match the voice and granularity of the existing entries. Read the top few before writing.

## Format

```ts
{
  version: 'vX.Y.Z',
  date: 'YYYY-MM-DD',   // today's date
  changes: [],
  sections: [
    { label: 'New Features', items: ['[Category] ...'] },
    { label: 'Changes',      items: ['[Category] ...'] },
    { label: 'Fixes',        items: ['[Category] ...'] },
  ],
}
```

Pick the version: minor bump (`v0.X.0`) for a release with new features, patch bump (`v0.X.Y`) for a small fixes-only release. Insert the new object as the first element of `CHANGELOG`.

## After writing

Confirm the file still parses (it is TypeScript) and that the footer now shows the new version. Commit on `development` (or wherever the release is being cut) with a short message.
