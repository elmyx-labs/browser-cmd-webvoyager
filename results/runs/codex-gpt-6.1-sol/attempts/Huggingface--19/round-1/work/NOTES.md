Selection: https://huggingface.co/models?pipeline_tag=summarization&language=en&sort=created
UI filters: Summarization, English; sort: Recently created. First entry: Mouserat/titlerat. Next entries: Immich/pipeline-error-propagation-dialogue-summarization-longt5-*.
Model card: https://huggingface.co/Mouserat/titlerat
Tags: Summarization, Transformers, Safetensors, Japanese, English, mt5, text2text-generation, title-generation, License: apache-2.0.
Card heading: titlerat v1. Japanese text says it reads Japanese/English requests and creates short titles (noun phrases) expressing subject and type, for chat history lists. Base: google/mt5-small. Does not generate responses.
Use model repository tokenizer with added <user>, </user>, <assistant>, </assistant> tokens. Input includes request and assistant response in these tags.
Card: weights and code Apache-2.0; model.safetensors FP32; tokenizer files; manifest includes weight SHA-256; Colab notebook.
Sidebar: Model size 0.3B params; tensor type F32; no inference provider deployment.
Training: 37,319 examples; full dataset unreleased. Sources: SFT-General-Japanese-60K 16,179; tagengo-gpt4 13,996; shisa-v2-sharegpt 5,847; ShareGPT-Processed 842; synthetic/self-authored refusal examples 433; self-authored animal dialogue examples 22. Some titles generated using Qwen3.5-4B.
Limitations: longer requests more topic mistakes; long English requests perform worse than long Japanese; titles do not guarantee factual correctness; unsupported languages may be copied verbatim or mixed with Japanese; harmful topics can appear in generated titles.
History: https://huggingface.co/Mouserat/titlerat/commits/main
Initial commit 2026-10-23T00:53:19Z; model/tokenizer upload 2026-10-23T00:53:57Z. UI groups these under Oct22 (America/New_York); latest README update 2026-10-27T05:30:15Z.
License-filtered newest-first listing also places Mouserat/titlerat first: https://huggingface.co/models?pipeline_tag=summarization&language=en&license=license:apache-2.0&sort=created . Current listing shows Updated 1 day ago, matching latest README update; original unfiltered listing was stale for updated/size values.
Final screenshot: model card viewport scrolled 70px, resized to 1280x723; name, English, Summarization, Apache-2.0, mT5-small base, 0.3B parameter count, F32, Colab and provider status visible together. This is the sole evidence image read.
