# Using the corpus with a language model

This guide is for developers who want a language model to answer questions about Swedish law from this corpus: by connecting an assistant through the MCP server, by building retrieval (RAG) over the corpus, or by fine-tuning a model. For asking questions in NotebookLM or a similar notebook tool without writing code, see [notebooks.md](notebooks.md).

Answers produced this way are not legal advice. The corpus is a snapshot: amendments published after you build your index or dataset are missing until you update it, and only the official publications are authentic.

## Which approach

| Approach | What it gives you | What it costs |
|---|---|---|
| **MCP server** | An assistant searches and reads the corpus through the static API; no index to build | Full-text search only, no semantic search |
| **Retrieval (RAG)** | Answers cite the exact SFS number and §, with the source URL; repealed text can be filtered out; a law change means re-indexing, not retraining | Answers are only as good as retrieval; questions that need many provisions at once are hard |
| **Instruction fine-tuning** (LoRA, QLoRA) | Teaches behaviour: answer in Swedish, always cite, say "I don't know" when the passages do not answer | Does not reliably store facts, and makes invented citations worse when used as a knowledge store |
| **Continued pretraining** | Teaches legal Swedish style and vocabulary | Knowledge frozen at training time, so the model cites repealed or invented § numbers with confidence; needs several GPUs or a cloud budget; general data must be mixed in to avoid forgetting |

Use retrieval as the default. Fine-tune only to change behaviour, and serve a fine-tuned model behind retrieval. By setup:

- **A laptop:** the MCP server, or retrieval with a 4-bit quantised model in Ollama or llama.cpp and a local embedding model.
- **One GPU:** retrieval plus a QLoRA adapter trained to answer from retrieved passages with citations. Unsloth lists about 6 GB of VRAM for QLoRA on an 8B model and about 22 GB for 16-bit LoRA ([requirements](https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements)).
- **Cloud:** optionally continued pretraining on SFS and case law, then instruction tuning, still served behind retrieval.

## The corpus in numbers

Measured on `main` on 2026-11-02: 54,786 documents, 975 MB, about 122 million words.

| Folder | Documents | Words |
|---|---|---|
| `corpus/case-law/reports` and `notices` | 16,475 | 56.0 M |
| `corpus/agency/regulations` | 5,468 | 13.9 M |
| `corpus/municipality/regulations` | 5,572 | 12.3 M |
| `corpus/region/county-regulations` | 11,649 | 11.0 M |
| `corpus/sfs/acts` | 3,000 | 10.1 M |
| `corpus/sfs/ordinances` | 6,591 | 8.3 M |
| `corpus/eu/` (regulations, directives, decisions, judgments) | 675 | 6.4 M |
| `corpus/sfs/treaties` | 3,515 | 2.1 M |
| `corpus/sfs/other` | 1,837 | 1.6 M |
| `corpus/fundamental-laws` | 4 | 36 k |

At roughly 3.5 to 4 characters per token for Swedish with common tokenizers, that is on the order of 200 million tokens. Measure with your model's tokenizer before planning a training run. `STATISTICS.md` has the current figures.

## Reading the documents

Each file in `corpus/` is Markdown with YAML frontmatter. The keys that matter for retrieval:

- `id`, `title`, `type`, `layer`, `number`: what the norm is (`sfs-1982-80`, "Lag (1982:80) om anställningsskydd", `act`, `sfs`, `1982:80`).
- `issued`, `in_force`, `repealed`, `amended_by`, `amended_through`: dates and amendments. Filter on `repealed: null` to keep current law.
- `source`, `source_sha256`, `fetched_at`: the official URL the text was read from, the hash of those bytes and when. Show `source` with every answer.
- `court`, `ecli` for case law; `celex` for EU law; `region_code` and `municipality_code` for county and municipal regulations.
- `text_source: ocr` marks text read from a scanned PDF by OCR. It can contain recognition errors; tell users when an answer rests on it.

The full list and formats are in [`docs/schema/frontmatter.schema.json`](../schema/frontmatter.schema.json).

In the body, the first line is a `#` heading with the title. Chapters are lines like `2 kap.` or `## 2 kap. Rubrik`, and sections start with a bold number: `**5 §**`, `**2 a §**`. A section that is about to change can appear twice: the current wording marked `/Upphör att gälla U:<date>/` and the coming one marked `/Träder i kraft I:<date>/`. Keep the marker in the chunk, or pick the version that applies on the date the question is about; never merge the two.

## Connecting through MCP

The quickest way to give an assistant the corpus is the MCP server in `mcp/` (standard library only). Build the API, then register the server with your MCP client:

```sh
python3 -I api/build.py --corpus corpus --out build/api/v1
```

```json
{
  "mcpServers": {
    "lagar": {
      "command": "python3",
      "args": ["-I", "mcp/server.py", "--api", "build/api/v1"]
    }
  }
}
```

`.mcp.json` in the repository already does this for clients that read it. Tools: `search_laws` (full-text search, filtered by layer and type), `get_document` (metadata and text by id), `list_layers`, `list_documents` and `get_report`. Ask the assistant to search, read the document, and quote the § with its `source` URL.

## Building retrieval

1. **Choose what to index.** Start with one area (SFS acts and ordinances, or one legal field) rather than all 122 million words: embedding everything on a CPU takes hours to days.
2. **Chunk by section.** Split statutes at `**N §**`, keeping the chapter and section in the chunk's metadata, and start every chunk with a citation line such as `3 kap. 5 § brottsbalken (1962:700)`. Split case law and long regulations at headings or paragraphs, around 512 to 1,024 tokens per chunk.
3. **Keep the metadata.** Store `id`, `number`, `title`, chapter, section, `in_force`, `repealed`, `layer` and `source` with each chunk, so you can filter (current law only, one layer) and cite.
4. **Embed.** Embedding models that handle Swedish:
   - **BGE-M3:** dense and sparse retrieval, 8,000-token context, a good fit for long sections.
   - **multilingual-e5-large:** strong on the [Scandinavian Embedding Benchmark](https://arxiv.org/abs/2406.02396).
   - **Qwen3-Embedding** (0.6B, 4B, 8B): strong on multilingual benchmarks; no Swedish-specific figure found.
   - **KBLab/sentence-bert-swedish-cased:** small and trained for Swedish.

   Build a small set of questions with known answers (the § that answers each) and compare models on it before choosing.
5. **Store.** LanceDB or Chroma for a laptop (LanceDB reads Parquet directly); Qdrant on a server for combined sparse and dense search with BGE-M3; pgvector if you already run Postgres.
6. **Generate.** Retrieve the top passages with `repealed` empty, and prompt the model to answer only from those passages, in Swedish, citing the citation line and the `source` URL of each passage it uses, and to say so when they do not answer the question.
7. **Measure.** Check answers on your question set for wrong or invented citations, not only for fluency.
8. **Stay current.** The corpus is synced daily from the official sources. Re-index the documents whose `source_sha256` changed since your last build (`git diff --name-only <old>..<new> -- corpus/` lists them).

### Models for Swedish

Rankings change often; check [EuroEval](https://euroeval.com) (the successor of ScandEval) for current Swedish results before choosing. At the time of writing:

- **Gemma 4 31B** was reported as the strongest open-weights model on EuroEval for Swedish ([Berget.ai, May 2026](https://berget.ai/en/blog/gemma-4-general-availability)); check its licence.
- **Qwen**, **Llama** and **Mistral** models are usable in Swedish; check their current scores.
- **Viking** (7B, 13B, 33B; Apache 2.0) is Nordic-focused, but its maker called the larger checkpoints not production-ready ([AMD](https://www.amd.com/en/blogs/2024/viking-7b-13b-33b-sailing-the-nordic-seas-of-multilinguality.html)).
- **GPT-SW3** (AI Sweden) is Swedish-trained but older, under a modified RAIL licence with use restrictions.

Serve locally with Ollama or llama.cpp (GGUF quantisations).

## Fine-tuning

Fine-tune for behaviour, on top of retrieval:

1. Generate training examples from the corpus: a question, the retrieved passages, and an answer that quotes and cites those passages. Include examples where the passages do not answer the question and the right answer says so.
2. Train a LoRA or QLoRA adapter with Unsloth (one GPU, fastest), Axolotl (configuration files, several GPUs) or TRL's `SFTTrainer`.
3. Evaluate the adapter behind your retrieval pipeline on the same question set, and compare it with the base model.

Keep case law out of training data: even anonymised judgments can hold residual personal data, and language models can reproduce training text. Use case law for retrieval only.

## Licensing

- **Statutes, ordinances, agency, county and municipal regulations, and court decisions** are free of copyright under 9 § upphovsrättslagen (1960:729), as [`NOTICE.md`](../../NOTICE.md) explains. Maps, images and some works in annexes keep their copyright: leave attachments out of datasets. Standards that regulations refer to (SIS and others) are copyrighted and are not in the corpus.
- **EU law** may be reused with attribution under the European Commission's reuse policy (Decision 2011/833/EU, with CC BY 4.0 as the default licence since 2019); only the Official Journal text is authentic.
- **Case law** is published anonymised, and the corpus holds only those versions. The GDPR still applies to any personal data that remains, which is another reason to use it for retrieval rather than training.
- **Publishing a trained model** may bring obligations under the EU AI Act for general-purpose models (a summary of training data, a copyright policy). Check them before you publish.

A dataset or model built from the corpus should say that it is not the official text and not legal advice, give the corpus commit it was built from, and link the official sources.

## Not available yet

These would make the steps above shorter; they are not in the repository yet:

- an export script that writes the corpus as a dataset (one record per document and one per §, as JSONL and Parquet), with filters for layer and current law;
- a published dataset on Hugging Face, versioned by corpus commit;
- a small retrieval example (BGE-M3, LanceDB, Ollama) with a Swedish question set, and a fine-tuning notebook.
