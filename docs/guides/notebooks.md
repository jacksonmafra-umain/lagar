# Asking questions about the law in a notebook tool

This guide is for anyone who wants to ask questions about Swedish law in plain language and get answers that point to the exact law and §, without writing code beyond copying one command. It covers Google NotebookLM and three open-source tools you run on your own computer. Developers who want to build their own retrieval or connect an assistant should read [llm.md](llm.md).

These tools answer from the files you give them. The answers are not legal advice: check every answer against the official text behind its source link. The files are a snapshot of the corpus on the day you download them; later amendments are missing until you download again.

## Get the files

Each law is one Markdown file in the `corpus/` folder, named after its number: Lag (1982:80) om anställningsskydd is `corpus/sfs/acts/1982-80.md`.

- **A few laws:** open the file on GitHub, then use the "Download raw file" button.
- **Many laws:** download the whole repository with *Code → Download ZIP* on the GitHub page and unzip it. It is large (about 1 GB unpacked).

The folders:

| Folder | What is in it | Documents |
|---|---|---|
| `corpus/fundamental-laws` | The four fundamental laws (regeringsformen and the others) | 4 |
| `corpus/sfs/acts` | Acts (lagar) | 3,000 |
| `corpus/sfs/ordinances` | Ordinances (förordningar) | 6,591 |
| `corpus/sfs/treaties`, `corpus/sfs/other` | Treaties and other SFS documents | 5,352 |
| `corpus/agency/regulations` | Agency regulations (föreskrifter) | 5,468 |
| `corpus/region/county-regulations` | County regulations (länsföreskrifter) | 11,649 |
| `corpus/municipality/regulations` | Municipal regulations (kommunala föreskrifter) | 5,572 |
| `corpus/case-law` | Court decisions (referat and notiser) | 16,475 |
| `corpus/eu` | EU regulations, directives, decisions and judgments in Swedish | 675 |

Counts are from 2026-11-02; `STATISTICS.md` has the current ones.

## Choose a topic, not everything

A notebook with the laws of one area answers better than one with the whole corpus. Some starting points:

- **Fundamental laws:** the four files in `corpus/fundamental-laws`.
- **Employment:** `corpus/sfs/acts/1982-80.md` (anställningsskydd), `1976-580.md` (medbestämmande), `1982-673.md` (arbetstid), `1977-480.md` (semester), `2008-567.md` (diskriminering).
- **Data protection:** `corpus/eu/regulations/32016r0679.md` (the GDPR) and `corpus/sfs/acts/2018-218.md` (dataskyddslagen).
- **Your kommun:** its files in `corpus/municipality/regulations` and your county's in `corpus/region/county-regulations` (both start with the code of the kommun or county), plus the fundamental laws.

## Google NotebookLM

NotebookLM is a Google service at <https://notebooklm.google.com>. You upload sources to a notebook and ask questions; answers cite the passages they come from.

### Limits

From Google's help pages (they say the limits can change):

- One source can hold up to 500,000 words or 200 MB ([source limits](https://support.google.com/notebooklm/answer/16269187)).
- Markdown (`.md`) files are accepted as they are ([file types](https://support.google.com/notebooklm/answer/16215270)).
- Sources per notebook: 50 on the free plan, 100 on Plus, 300 on Pro, 500 on Ultra ([plans](https://support.google.com/gemininotebook/answer/16213268)).

So a notebook takes up to 50 laws as single files on the free plan. For more, combine them into bundles (below).

### Swedish

Google says NotebookLM supports more than 80 languages ([help](https://support.google.com/notebooklm/answer/16164461)) but does not list them. Set the output language to Swedish in the notebook's settings, and ask in Swedish.

### Privacy

The laws are public, but your questions may not be. On a personal Google account, Google says your sources and questions are not used to train its models and are not reviewed by people, unless you send feedback (the thumbs up or down), which makes that conversation available for review. On a Workspace or Education account there is no human review and no training. Check [Google's privacy notes](https://support.google.com/notebooklm/answer/16164461) before asking about anything confidential.

### Combine files into bundles

To fit more laws into one notebook, combine them into bundle files of at most 400,000 words each, leaving room under the 500,000-word limit. Each law keeps its title as a heading and a line with its official source link, so citations stay traceable. `--only-in-force` leaves repealed laws out.

You need Python 3 (on Windows, type `py` instead of `python3`). In the unzipped repository folder, run the export script with an output folder, your plan and the folders or files you want:

```sh
python3 -I scripts/export_corpus.py --target notebooklm --only-in-force --tier free --out notebook/employment corpus/fundamental-laws corpus/sfs/acts/1982-80.md corpus/sfs/acts/1976-580.md
```

`--tier` is `free`, `plus`, `pro` or `ultra`. If the selection needs more sources than that plan allows, the script says how many it needs and writes nothing; choose fewer files or a larger plan. `--layers sfs,eu` keeps only those layers of the folders you name.

Upload the `bundle-*.md` files from the output folder to your notebook. `manifest.json` in the same folder lists the laws in each bundle, with their word counts. What fits, measured on 2026-11-02 with laws in force only:

| Selection | Bundles | Plan it fits |
|---|---|---|
| `corpus/fundamental-laws` | 1 | Free |
| `corpus/sfs/acts` | 16 | Free |
| `corpus/sfs` (acts, ordinances, treaties, other) | 30 | Free |
| `corpus` (everything) | 274 | Pro |

A document longer than one bundle is split at chapter or § boundaries, and each part's heading says which part it is, such as `(part 1/2)`. Seven documents, all county or agency regulations, are split this way.

### Ask well

- Ask the notebook to cite the law and § for every statement, and to say so when the sources do not answer the question.
- Click each citation to see the passage it comes from, and open the source link to read the official text.
- A section about to change can appear twice, marked `/Upphör att gälla U:<date>/` (current wording) and `/Träder i kraft I:<date>/` (the coming one). Ask which version applies on the date you care about.
- Text marked as read by OCR (from scanned PDFs) can contain recognition errors.

## Open-source tools on your own computer

These run on your computer with a local language model, so your questions stay there. They split files into small pieces and search them, so import one file per law (not bundles): citations then point to a single law. The export script writes one file per law with its number, dates and official source link at the top, so an answer is easy to check against the official text:

```sh
python3 -I scripts/export_corpus.py --target files --only-in-force --out notebook/files corpus/fundamental-laws corpus/sfs/acts
```

The files land in one folder per layer, named after each document's id. Embedding (indexing) many files takes time on an ordinary computer, from minutes for a topic to days for the whole corpus, so start with a topic.

You need a local model runner: install [Ollama](https://ollama.com) and download a chat model that handles Swedish (see the model notes in [llm.md](llm.md#models-for-swedish)) and a multilingual embedding model such as `bge-m3`.

### AnythingLLM

The easiest for people who do not use the command line: a desktop app for macOS, Windows and Linux ([GitHub](https://github.com/Mintplex-Labs/anything-llm)).

1. Install the desktop app and choose Ollama as the language model and as the embedder.
2. Create a workspace for your topic and upload the law files.
3. Ask questions; answers show the files they used.

AnythingLLM sends anonymous usage data unless you turn it off in its settings (privacy, telemetry).

### Open Notebook

The closest to NotebookLM: notebooks, sources, notes and cited answers ([GitHub](https://github.com/lfnovo/open-notebook)). It runs with Docker Compose; the web page is at `http://localhost:8502`.

It has no password by default. Keep it reachable only from your own computer (bind it to `127.0.0.1`), or set `OPEN_NOTEBOOK_PASSWORD` before you start it.

### Open WebUI

A chat interface for Ollama with knowledge bases you can attach to a chat ([GitHub](https://github.com/open-webui/open-webui)). Runs with Docker. Create a knowledge base, upload the law files, and attach it to a chat.

## Coming later

Prebuilt packs (fundamental laws, employment, data protection, all acts) to download without the repository are not available yet.
