# LaserWong pipeline comparison

Source checked at commit `4f3572db16b8c57641e11222511203ecd6cb0e58`, the repository's latest commit at inspection time. The public source was retrieved directly through GitHub's API. Links below pin the inspected source.

## Scheduling and execution

LaserWong's [daily-update.yml](https://github.com/LaserWong/LaserWong.github.io/blob/4f3572db16b8c57641e11222511203ecd6cb0e58/.github/workflows/daily-update.yml) uses GitHub Actions:

1. A cron trigger (`17 4-14 * * 1-5`, in UTC) attempts runs hourly at minute 17 during that window. Manual and selected source-change triggers also exist.
2. A guard checks the New York weekday/date and skips scheduled generation when both daily archives already exist. The repeated triggers are retry opportunities, not instructions to regenerate the completed digest eleven times.
3. An Ubuntu runner checks out the repository, installs Python and dependencies, and receives DEEPSEEK_API_KEY from GitHub Actions secrets.
4. Python generates the archives and homepage. The workflow commits generated output and pushes with the workflow's contents-write permission.

GitHub supplies the execution context and repository access directly; no ChatGPT schedule needs to inherit a published environment. GitHub schedules may be delayed under load; they are not exact-time guarantees. See [GitHub's scheduling documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

## Selection and summaries

The [Chinese generator](https://github.com/LaserWong/LaserWong.github.io/blob/4f3572db16b8c57641e11222511203ecd6cb0e58/tools/generate_arxiv_daily.py) reads the first New submissions section of the category listings, applies category and keyword rules, and orders retained papers by category and arXiv ID. The filter is Python logic, not a model deciding a personalized top ten. It attempts to summarize the retained papers with DeepSeek and has fallbacks. The [configuration](https://github.com/LaserWong/LaserWong.github.io/blob/4f3572db16b8c57641e11222511203ecd6cb0e58/arxiv_daily_config.json) names deepseek-reasoner, enables summaries, and sets a per-request max_tokens of 3072; this is a cap, not actual usage or a whole-day budget.

Its [October 6 Chinese archive](https://github.com/LaserWong/LaserWong.github.io/blob/4f3572db16b8c57641e11222511203ecd6cb0e58/arxiv_daily/2026-10-06/papers.json) contains 232 entries: 193 labeled deepseek and 39 local-fallback. It therefore processes a much broader selection than our intended 10–20 papers. Summary source labels alone do not reveal exact token charges.

The [English generator](https://github.com/LaserWong/LaserWong.github.io/blob/4f3572db16b8c57641e11222511203ecd6cb0e58/tools/generate_arxiv_daily_cornell.py) also uses keyword/category filtering and a fixed sort order. OpenAI summaries are optional and default to disabled. Its current config does not enable them, and the workflow supplies only the DeepSeek key. This archive uses the local fallback path in that configuration, rather than a scheduled ChatGPT conversation.

DeepSeek API usage is billed separately for model tokens; it is not included in ChatGPT Plus. See [DeepSeek's pricing documentation](https://api-docs.deepseek.com/quick_start/pricing/). The inspected repository's configured model name should be checked against the provider's current supported models before adopting its code.

## Current daily-arXiv pipeline

The comparison above records the earlier source inspection. daily-arXiv now uses GitHub Actions to archive arXiv's official Atom feeds, and local Codex with the existing ChatGPT subscription to select and explain 10–20 papers, normally ten. A protected Python publisher delivers the digest and equation-pronunciation companion together. GitHub Actions then generates audio and deploys the website.

This implementation does not use the earlier cloud-environment prompt or a paid model API. Collection and publication use deterministic Python; the research model runs locally. See the [technical guide](technical-setup.md) and [active prompt](../prompts/local-research.md) for the current configuration.
