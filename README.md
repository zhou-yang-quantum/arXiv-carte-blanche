# daily-arXiv

A personal daily arXiv digest and reading archive. Each entry ranks 10–20 newly announced papers and explains the main result, background and motivation, and why it matters for the reader.

**[Read the website](https://zhou-yang-quantum.github.io/daily-arXiv/)**

The current selection focuses on theoretical physics and quantum information: quantum field theory, non-equilibrium physics, quantum error correction, quantum simulation, quantum algorithms, and exactly solvable models. You can adapt the same setup to your own interests.

## What it does

- Browse by date and filter by topic.
- Read summaries with equations and links to the original arXiv papers.
- Hide the archive sidebar, switch to compact view, or expand individual paper details.
- Save papers locally or sync them across devices with your own Dropbox account.
- Switch between light and dark reading modes.
- Ask GPT about any paper: open ChatGPT with the complete digest item, original arXiv links, and a prepared prompt for physics and maths questions grounded in the paper. You may need to sign in and press Send in ChatGPT.
- Listen to available recordings with a chapter playlist, playback speed controls, and a ZIP download of individual paper MP3s.

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
| [prompts/researcher-profile.md](prompts/researcher-profile.md) | Set your durable interests and knowledge calibration. The research prompt instructs each fresh run to read this profile before screening papers. |
| [preferences.json](preferences.json) | Match the interests and criteria shown on the website to your prompt. This file does not control generation. |
| [local-pipeline.json](local-pipeline.json) | Set the arXiv `categories` to scan. For automation, also choose your `start_date`, timezone, time, model, and effort. |

For example, replace the prompt's topic paragraph with your preferred fields and ask for explanations at your own level. Keep the default ten papers, with up to twenty when warranted; the importer currently enforces 10–20. Edits affect future digests, so existing entries remain as examples until you replace them deliberately.

To host your own copy, enable Actions in your fork and select **Settings → Pages → Source → GitHub Actions**. Push to `main` to publish. Update the repository link in `site/index.html` and this README's website link. The [technical setup guide](docs/technical-setup.md#fork-specific-settings) lists the additional repository URLs to change before enabling automatic publishing or audio.

For interests outside the current physics topics, the same guide explains how to adjust the topic filters.

Future digests use motivation-first summaries, paper-specific background explanations calibrated to the profile, and a reasoned assessment of scientific significance in **Why it matters?** Update the prompt or profile to carry reading feedback into later runs.

## Add digests

**Manually:** save a digest as UTF-8 Markdown at `incoming/YYYY-MM-DD.md`, following the [format in the technical guide](docs/technical-setup.md#digest-format). Run `npm run build` to validate it, then commit the Markdown and push to `main`. GitHub Actions parses it during the build and deploys the updated archive; you do not need to commit generated JSON or `dist/`.

**Automatically:** the current setup runs locally on Windows with Codex signed in through ChatGPT and GitHub CLI signed in to the destination repository. A Codex task runs at 10:00 on weekdays, and a startup watcher catches up missed days while the computer and Codex app are running. This uses the existing ChatGPT login with no paid model API fallback; account usage limits still apply.

See **[Technical setup and agent reference](docs/technical-setup.md)** for the exact research prompt, sanitized scheduled-task prompt, installation steps, catch-up behavior, GitHub Actions workflows, and validation commands. Local schedules and logins must be set up separately for each person; cloning the repo does not create them.

## To-do: future implementations

- [ ] Improve date browsing:
  - [x] Organize the left sidebar by month, then by date within each month (month/year headings are already implemented).
  - [ ] When the left sidebar is hidden, replace the date dropdown with a calendar icon to the right of the title. Clicking the icon opens a calendar view with available dates highlighted and unavailable dates greyed out.
- [ ] Add an **All** button to the right of **Latest**:
  - [ ] Display all papers, ordered from newest to oldest.
  - [ ] Paginate with 10 papers per page.
  - [ ] Display papers without numbering.
- [ ] Add a **Save** button to the online audio player to save the paper currently playing.

## Credits

Inspired by [LaserWong/LaserWong.github.io](https://github.com/LaserWong/LaserWong.github.io). Markdown and equations use [Marked](https://github.com/markedjs/marked) and [KaTeX](https://github.com/KaTeX/KaTeX); their licenses are included in the published assets. [Audio implementation and credits](audio/README.md).
