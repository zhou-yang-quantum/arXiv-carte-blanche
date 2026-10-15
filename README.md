# daily-arXiv

A personal daily arXiv digest and reading archive. Each entry ranks 10–20 newly announced papers and explains the main result, background and motivation, and why it matters for the reader.

**[Read the website](https://zhou-yang-quantum.github.io/daily-arXiv/)**

The current selection focuses on theoretical physics and quantum information: quantum field theory, non-equilibrium physics, quantum error correction, quantum simulation, quantum algorithms, and exactly solvable models. You can adapt the same setup to your own interests.

## What it does

- Browse by date and filter by topic.
- Read summaries with equations and links to the original arXiv papers.
- Save papers locally or sync them across devices with your own Dropbox account.
- Switch between light and dark reading modes.
- Copy a dated digest or individual paper for voice reading, or listen to recordings when available.

The website is static HTML/CSS/JavaScript. Local Codex generates the digests; GitHub Actions collects arXiv source data and builds and deploys the website. Browsing, building, and manual digest imports need no model API key.

Dropbox sync is optional and needs a one-time public app-key setting. Follow the [Dropbox setup guide](docs/dropbox-sync.md); no app secret, paid backend, or model API is needed. Without a connection, saves stay in the browser.

## Try it locally

Clone this repository, or fork it on GitHub and clone your fork:

```sh
git clone https://github.com/zhou-yang-quantum/daily-arXiv.git
cd daily-arXiv
```

With Docker Desktop running:

```sh
docker compose up --build -d --wait
```

Open **http://localhost:8080**. Run the same command after edits to rebuild; use `docker compose down` to stop.

Alternatively, with Node.js 22+ and Python 3.11+:

```sh
npm ci
npm run build
npm run preview
```

Open **http://127.0.0.1:4173**.

## Make it your own

The minimum changes for a personalized digest are:

| File | What to change |
| --- | --- |
| [prompts/local-research.md](prompts/local-research.md) | Set your interests, exclusions, assumed background, and what makes a paper useful to you. This is the prompt the local generator actually reads. Keep its dated output format. |
| [preferences.json](preferences.json) | Match the interests and criteria shown on the website to your prompt. This file does not control generation. |
| [local-pipeline.json](local-pipeline.json) | Set the arXiv `categories` to scan. For automation, also choose your `start_date`, timezone, time, model, and effort. |

For example, replace the prompt's topic paragraph with your preferred fields and ask for explanations at your own level. Keep the default ten papers, with up to twenty when warranted; the importer currently enforces 10–20. Edits affect future digests, so existing entries remain as examples until you replace them deliberately.

To host your own copy, enable Actions in your fork and select **Settings → Pages → Source → GitHub Actions**. Push to `main` to publish. Update the repository link in `site/index.html` and this README's website link. The [technical setup guide](docs/technical-setup.md#fork-specific-settings) lists the additional repository URLs to change before enabling automatic publishing or audio.

For interests outside the current physics topics, the same guide explains how to adjust the topic filters.

## Add digests

**Manually:** save a digest as UTF-8 Markdown at `incoming/YYYY-MM-DD.md`, following the [format in the technical guide](docs/technical-setup.md#digest-format). Run `npm run build` to validate it, then commit the Markdown and push to `main`. GitHub Actions parses it during the build and deploys the updated archive; you do not need to commit generated JSON or `dist/`.

**Automatically:** the current setup runs locally on Windows with Codex signed in through ChatGPT and GitHub CLI signed in to the destination repository. A Codex task runs at 10:00 on weekdays, and a startup watcher catches up missed days while the computer and Codex app are running. This uses the existing ChatGPT login with no paid model API fallback; account usage limits still apply.

See **[Technical setup and agent reference](docs/technical-setup.md)** for the exact research prompt, sanitized scheduled-task prompt, installation steps, catch-up behavior, GitHub Actions workflows, and validation commands. Local schedules and logins must be set up separately for each person; cloning the repo does not create them.

## Credits

Inspired by [LaserWong/LaserWong.github.io](https://github.com/LaserWong/LaserWong.github.io). Markdown and equations use [Marked](https://github.com/markedjs/marked) and [KaTeX](https://github.com/KaTeX/KaTeX); their licenses are included in the published assets. [Audio implementation and credits](audio/README.md).
