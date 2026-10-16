# arXiv carte blanche

<img src="site/chef-bot.svg" alt="Chef-bot serving a dish" width="112" height="112" align="right">

*Carte blanche* means giving the chef a free hand: you share your tastes, and let them decide what to serve. arXiv supplies the raw ingredients; AI selects the papers and cooks them into an appetizing daily menu of ideas, explanations, and background tailored to you.

I started this project because I wanted to listen to arXiv papers during my commute. It grew into a personal daily digest and reading archive, with recordings for listening on the go.

**[Read the website](https://zhou-yang-quantum.github.io/arXiv-carte-blanche/)**

## Le menu

- **A daily digest to your taste.** AI selects and ranks 10–20 newly announced papers, explaining the main result, motivation, background, and why each paper matters. Both the selection and the depth of explanation are catered to the researcher's interests and knowledge.
- **Audio for the commute.** Accompanying recordings include experimental maths pronunciations: equations are given spoken English readings, with pauses and phrasing to help them make sense by ear. Listen by paper or play the day's menu, with playback speed controls and downloadable MP3s.
- **Save something for later.** Bookmark papers from the page or audio player, and sync your saved papers across devices through your own Dropbox account.

*Bon appétit!*

The published menu reflects my own knowledge and interests in theoretical physics and quantum information: quantum field theory, non-equilibrium physics, quantum error correction, quantum simulation, quantum algorithms, and exactly solvable models. For a menu of your own, [fork the repository](https://github.com/zhou-yang-quantum/arXiv-carte-blanche/fork) and ask your AI to adapt it to your tastes. See [Make it your own](#make-it-your-own) below.

## What it does

- Browse a monthly calendar with available digests highlighted, jump to a month or year, and filter by topic.
- Read summaries with equations and links to the original arXiv papers.
- Hide the archive sidebar, switch to compact view, or expand individual paper details.
- Switch between light and dark reading modes.
- Ask GPT about any paper: open ChatGPT with the complete digest item, original arXiv links, and a prepared prompt for physics and maths questions grounded in the paper. You may need to sign in and press Send in ChatGPT.

The website is static HTML/CSS/JavaScript. Local Codex generates the digests; GitHub Actions collects arXiv source data and builds and deploys the website. Browsing, building, and manual digest imports need no model API key.

Dropbox sync is optional and needs a one-time public app-key setting. Follow the [Dropbox setup guide](docs/dropbox-sync.md); no app secret, paid backend, or model API is needed. Without a connection, saves stay in the browser.

## Try it locally

To preview the existing setup on your computer, clone this repository:

```sh
git clone https://github.com/zhou-yang-quantum/arXiv-carte-blanche.git
cd arXiv-carte-blanche
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

The paper choices, assumed background, and explanations here are tailored to me. To make your own version, **fork** the repository on GitHub, then **clone your fork** to your computer. The fork gives you your own GitHub repository to publish from; cloning gives you a local copy to work on. Cloning alone is enough for a local preview.

Then ask your AI to adjust the recipe. For example:

> Make this my daily arXiv menu. My research interests are [...]. I already know [...], and I would like more explanation of [...]. Update the research prompt, researcher profile, public preferences, and arXiv categories to match my tastes and knowledge level. Keep the website and audio pipeline working.

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

- [ ] Add an **All** button to the right of **Latest**:
  - [ ] Display all papers, ordered from newest to oldest.
  - [ ] Paginate with 10 papers per page.
  - [ ] Display papers without numbering.
- [ ] Use a dedicated maths and physics speech engine, or develop a standalone engine for this purpose.

## Credits

Inspired by [LaserWong/LaserWong.github.io](https://github.com/LaserWong/LaserWong.github.io). Markdown and equations use [Marked](https://github.com/markedjs/marked) and [KaTeX](https://github.com/KaTeX/KaTeX); their licenses are included in the published assets. [Audio implementation and credits](audio/README.md).
