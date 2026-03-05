---
name: flutter-appstore-doc-ui-kit
description: Generate a launch-ready app package for App Store submission: a complete Markdown feature document plus Apple-style UI design images for each page and a square-corner app icon. Use when the user wants a Flutter app concept/spec constrained to FVM Flutter 3.35.1, offline-first (no backend), camera + photo library permissions, anti-saturation positioning, and no TODO/temp placeholders.
---

# Flutter AppStore Doc + UI Kit

Generate a full deliverable pack for an App Store-ready app idea:

- `docs/app-feature-spec.md` (complete product/function spec)
- `ui/*.svg` (Apple-style page design images)
- `icon/app_icon_1024.png` + `icon/app_icon_1024.svg` (square-corner icon)

## Workflow

1. Confirm core inputs.
2. Generate Markdown feature doc (no TODO/temp data).
3. Generate Apple-style page mockup images.
4. Generate square-corner app icon image.
5. Validate App Store review-risk checklist.

## 1) Required Inputs

Collect/confirm:

- App name
- Target language(s)
- Preferred app direction (if none, pick a low-saturation utility direction)
- Optional color style

Hard constraints to enforce:

- Tech stack: Flutter via **FVM Flutter 3.35.1**
- Includes **camera** + **photo library** permissions
- Avoid over-saturated app categories and avoid risky claim patterns
- No backend server required
- No TODO placeholders or temporary/fake data sections
- Focus on complete v1 only (no future-roadmap content)
- Can include general capabilities: i18n, dark mode, accessibility, privacy-first local storage
- App icon must be **square-corner** (not rounded)

## 2) Generate Deliverables

Run:

```bash
python3 scripts/generate_appstore_pack.py \
  --app-name "SnapSort" \
  --out ./out/snapsort \
  --locales "en,zh-Hans" \
  --primary-color "#0A84FF"
```

Outputs:

- `docs/app-feature-spec.md`
- `ui/page-01-home.svg` ... `ui/page-08-settings.svg`
- `icon/app_icon_1024.png`
- `icon/app_icon_1024.svg`

## 3) Quality Validation

Before handing off:

- Feature doc explicitly states FVM Flutter 3.35.1
- Camera + photo permissions appear in both feature and privacy sections
- No backend dependency appears in architecture or data flow
- No TODO/TBD/temp/placeholder language
- UI images cover all listed key pages in spec
- Icon is visually square (no rounded corner mask baked into source)

## 4) App Store Safety Guidance

Use `references/review-safety-checklist.md` and keep copy conservative:

- No medical/financial/legal guarantee claims
- No “instant earnings” or manipulative wording
- Permission usage tied to clear user-triggered actions
- Privacy text explicitly local-first and user-controllable

## Notes

- This skill creates design/spec artifacts, not Flutter code.
- If user also needs implementation scaffolding, create a separate Flutter build skill.
