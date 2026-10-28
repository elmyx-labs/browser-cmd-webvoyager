Evidence read through browser-cmd on 2026-10-27:
- https://huggingface.co/api/models?pipeline_tag=summarization&filter=en&sort=createdAt&direction=-1&limit=5 : newest result Mouserat/titlerat, createdAt 2026-10-23T00:53:19.000Z; tags en, ja, summarization, license:apache-2.0. Next result created 2026-10-20.
- https://huggingface.co/api/models?pipeline_tag=summarization&filter=en&sort=createdAt&direction=-1&limit=1&full=true : author Mouserat, lastModified 2026-10-27T05:30:15.000Z; mt5; transformers; safetensors.
- https://huggingface.co/Mouserat/titlerat/raw/main/README.md : Japanese/English title generation for chat histories; google/mt5-small; short noun-phrase title, not response text; 37,319 training examples; weights and code Apache-2.0; FP32 safetensors; repo tokenizer includes special user/assistant tokens. Limitations: topic errors for long requests, long English inputs worse than Japanese; unsupported languages can mix Japanese. Dataset itself not yet public.
- https://huggingface.co/Mouserat/titlerat/raw/main/config.json : MT5ForConditionalGeneration, encoder-decoder, eight encoder and eight decoder layers, float32.
- https://github.com/huggingface/huggingface_hub/blob/main/docs/source/en/guides/search.md : official docs confirm list/filter/sort method for Hub repositories.
- HF HTML directory and model pages repeatedly returned 429, including one retry-clean and other entry points. Raw model card and API accessible.
- Newer untagged medical summarizer ritujaa1/qwen05-med-summarizer-gguf created October 26, Apache 2.0, but no language metadata. English-filtered latest is titlerat. Do not conflate updated and created timestamps.

Second investigation:
- Full titlerat README confirms 433 synthetic/self-created refusal examples, 22 self-created animal dialogues, some titles generated with Qwen/Qwen3.5-4B, and an Open in Colab link. These claims were sourced correctly but concern a community model, not the final selected HF model.
- English-unfiltered latest summarization listing confirms newer Oct26 ritujaa1 Qwen/Llama and Oct23 rshahbaz Command R7B. Read all cards; publishers are community accounts, no HF authorship.
- HuggingFaceTB author list (no language filter) latest nanowhale base/chat Apr24 2026, GSM8K models Apr3/Mar25 2026, SmolLM3 checkpoints Jul20 2025, ONNX Jul8 2025, SmolLM3 Jul8 2025.
- nanowhale card: educational architecture demo, no summarization claim, generations often incoherent/factually wrong, not suitable for production. GSM8K cards explicitly math-specific.
- HuggingFaceH4 newest entries were checked without language filter. KD-Tinker and SmolLM3 QAT baseline cards are empty generated templates with language/license/use unspecified; latest Qwen3-4B repo expansion reports no files/card. Not documented qualifying releases.
- Official HF SmolLM3 blog read through browser-cmd: Published July8 2025; from Hugging Face authors; 3B, 11.2T training tokens, six native languages including English, 64K trained context/128K YaRN; decoder GQA/NoPE.
- Official SmolTalk2 README states dataset corresponds to three SmolLM3 post-training phases; SFT smollm3_smol-summarize has 96061 rows. This establishes actual summarization training, not an inference from an English tag.
- Official github.com/huggingface/smollm calls these models 'from Hugging Face' and names SmolLM3 newest language family.
