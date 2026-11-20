# Kanz team

> **This branch** (`kanz-team` in Egy-to-tokyo-automation) is KanzMS/kanz-team's `dev` branch, restyled as the
> **فريق كنز** tab of the Kanz Market Close site: its colours, fonts, header and tabs. That repo's **Deploy website**
> workflow builds it into `team/` (`SITE_BASE=/Egy-to-tokyo-automation/team/`); run that workflow after changing this
> branch. The gh-pages deploy workflow is removed here; KanzMS/kanz-team keeps its own.

A site for the Kanz team: a library of logos and designs that copy on click, the brand docs, and templates for making posts. A static React site, deployed to GitHub Pages from the `dev` branch, using MokhbirPro's design system.

**The site is public.** There is no sign-in, so anyone with the URL can read everything in `content/`. Don't add anything that isn't OK to share.

## Run it

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173/kanz-team/.

To check the production build, run `npm run build && npm run preview` in `frontend/`.

## Deploy

Every push to `dev` builds the site through `.github/workflows/pages.yml` and publishes the result to the `gh-pages` branch, which GitHub Pages serves at https://kanzms.github.io/kanz-team/. Don't edit `gh-pages` by hand: each deploy replaces it.

The site is served from a subfolder named after the repository. If the repository is renamed, change `base` in `frontend/vite.config.ts`.

## Add content

Add the file to `content/` and push to `dev`. When running locally, restart `npm run dev` to pick it up.

- **Logos and designs:** put a PNG, JPG, WebP or SVG in `content/assets/<Category>/`. The folder is the section title and the filename is the name (`kanz-logo-white.png` shows as "Kanz logo white").
- **Docs:** put a Markdown file in `content/docs/`, named in lowercase with hyphens:

  ```markdown
  ---
  title: Page title
  summary: One line for the list.
  icon: description   # a Material Symbols name
  order: 5
  ---
  ```

- **Templates:** each one is a React page in `frontend/src/templates/<name>/`, listed in `frontend/src/templates/index.ts`. The page uses the site's controls; the template's own drawing code (such as `workshop/engine.js`) holds its design and colours. Whatever a template embeds, such as photos, is public.
- **Workshop CTA:** the StreamYard promo code overlay, in the Workshop CTA tab. Only the code changes there; the Arabic box and the name bar are pre-rendered frames in `frontend/src/workshop-cta/base_top.png` and `base_bottom.png`, so changing the box's text or design means rendering those again. `engine.js` draws the code tag and writes the GIF: 91 frames with one held so the loop lasts 10 minutes, under StreamYard's 3 MB and 108-frame limits.

## Copying

Click-to-copy needs https or localhost, because browsers block clipboard images on plain http. Everything is copied as a PNG; SVGs are rasterised at 2048px on the longest side.
