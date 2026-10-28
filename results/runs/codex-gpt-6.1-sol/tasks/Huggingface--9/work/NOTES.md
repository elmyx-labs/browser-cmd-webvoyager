2026-10-27. HF Translation models, Most downloads sort, name search en-ja:
https://huggingface.co/models?pipeline_tag=translation&sort=downloads&search=en-ja
First results: Helsinki-NLP/opus-mt-ja-en 26.1k; Helsinki-NLP/opus-mt-en-jap 8.09k; staka/fugumt-en-ja 4.7k. Search includes fuzzy/reversed matches, so direction and language tags must decide relevance.
https://huggingface.co/Helsinki-NLP/opus-mt-ja-en: source languages ja, target en; 26,115 downloads last month; Tatoeba.ja.en BLEU 41.7 chr-F 0.589.
https://huggingface.co/Helsinki-NLP/opus-mt-en-jap: source en, target jap; language tags English and jap; 8,086 downloads last month; bible-uedin.en.jap BLEU 42.1 chr-F 0.960. Need resolve jap tag rather than assume Japanese.
https://huggingface.co/staka/fugumt-en-ja: source language en, target language ja; English and Japanese tags; 4,700 downloads last month. Eval results: tatoeba (randomly selected 500 sentences), source en, target ja, BLEU 32.7; (*1) sacrebleu --tokenize ja-mecab.
Final interpretation: en-ja means English → Japanese. Under Translation + English and Japanese filters + Most downloads + en-ja search, staka/fugumt-en-ja is the first matching direction, after the reverse-direction opus-mt-ja-en. The en-jap model disappears with the Japanese filter and is not treated as Japanese.
Screenshot: final.png, genuine 1440x1600 viewport resized to 1152x1280, showing staka/fugumt-en-ja, source en, target ja, Downloads last month 4,700, Tatoeba randomly selected 500 sentences, BLEU 32.7, sacrebleu --tokenize ja-mecab. No banner or dialog covers evidence. Ranking controls apply to list page, not model card.
Full-ranking check, 2026-10-27: https://huggingface.co/models?pipeline_tag=translation&language=ja,en&sort=downloads has empty Filter by name; Most downloads; first facebook/nllb-200-distilled-600M 969k, next distilled1.3B501k, 3.3B261k.
Winner card https://huggingface.co/facebook/nllb-200-distilled-600M: Downloads last month 968,642. Expanded 196 languages showed English and Japanese. Intended Use states single sentence translation among 200 languages. Metrics states BLEU, spBLEU, chrF++; XSTS human evaluation and toxicity measurement. Evaluation Data states Flores-200.
Card checkpoint metrics link https://tinyurl.com/nllb200densedst600mmetrics downloaded successfully via browser to media/browser/downloads/metrics.csv. Header direction,chrf++; eng_Latn-jpn_Jpan,23.6; jpn_Jpan-eng_Latn,50.2. Read downloaded CSV locally. Official fairseq modeling README same metrics URL for 600M distilled checkpoint; other non54.5B checkpoints provide only chrF++ on sampled directions including all402 English-centric directions.
Final replacement screenshot: media/browser/browser-0002.png is actual1440x1680 viewport of NLLB600M model card, resized with sips -Z1280 to final.png1097x1280. Only rewritten final.png was read as evidence image this turn. Name968,642downloads, BLEU/spBLEU/chrF++, XSTS/toxicity andFlores200 visible without overlay.
Dedicated en-ja focus check, full ranking no name search:
https://huggingface.co/lmg-anon/vntl-llama3-8b-v2-gguf —25,071 downloads last month. Summary: purpose is translating Japanese visual novels to English. Prompt alternates Japanese source and English target. Direction ja→en.
https://huggingface.co/sugoitoolkit/Sugoi-14B-Ultra-GGUF —6,386 downloads. Ideal Use Cases Japanese→English especially game dialogue/RPG text. System prompt says translate Japanese to English and always respond in English. It says target can be changed in prompt quality may vary; stated focus remains ja→en.
https://huggingface.co/ModelSpace/GemmaX2-28-9B-v0.1 —4,788 downloads. Model description: multilingual28languages. Not en-ja focused.
https://huggingface.co/Helsinki-NLP/opus-mt-mul-en —target groupEnglish, target languageeng. Direction multilingual→English.
https://huggingface.co/Unbabel/wmt22-comet-da —6,674 downloads. COMET evaluationmodel outputs quality score, not translation generation.
Higher-ranked multilingual models read with browser-cmd pages:
https://huggingface.co/tencent/Hy-MT2-30B-A3B-GGUF —among33languages.
https://huggingface.co/facebook/nllb-200-1.3B —among200languages.
https://huggingface.co/facebook/mbart-large-50-many-to-many-mmt —any pair50languages.
https://huggingface.co/google/madlad400-3b-mt —400+languages, over450 insummary.
https://huggingface.co/tencent/HY-MT1.5-1.8B-GGUF —mutual translation33languages.
https://huggingface.co/tencent/Hy-MT2-1.8B —among33languages.
https://huggingface.co/tencent/HY-MT1.5-7B-GGUF —mutualtranslation33languages.
https://huggingface.co/JustFrederik/nllb-200-distilled-600M-ct2-int8 —196language tags, NLLBconversion.
https://huggingface.co/mradermacher/Hunyuan-MT-7B-GGUF —36language tags.
https://huggingface.co/tencent/Hy-MT2-7B —among33languages.
https://huggingface.co/alirezamsh/small100 —multilingual100languages.
https://huggingface.co/Mungert/Hunyuan-MT-7B-GGUF —primarilymutualtranslation33languages.
Previously verified NLLB600M,1.3Bdistilled,3.3B cards explicitly200languages; opus-mt-ja-en sourceja targeten26,115downloads.
Remaining higher-ranked cards checked via browser-cmd pages:
https://huggingface.co/facebook/mbart-large-cc25 —pretrained multilingualmbart,25languages.
https://huggingface.co/unsloth/Hy-MT2-7B-GGUF —translationamong33languages.
https://huggingface.co/Xenova/nllb-200-distilled-600M —196languages,NLLBONNX.
https://huggingface.co/mradermacher/Hy-MT2-7B-i1-GGUF —36languages,quantizedHy-MT2.
https://huggingface.co/infosave/Hy-MT2-cmf —33languageHy-MT2family.
https://huggingface.co/tencent/HY-MT1.5-1.8B —mutualtranslation33languages.
Conclusion for requested en→ja focus: staka/fugumt-en-ja is highest qualifying in full Translation+English+Japanese Mostdownloads ranking without name search, after inspecting27higher-rankedentries. Higher pair-focused entries opus-mt-ja-en26,115,VNTL25,071,Sugoi14BUltra6,386areja→en. Otherhigherentriesarebroader multilingual or COMETevaluation. Winner sourceen,targetja;4,700downloads;BLEU32.7,Tatoeba500randomsentences,sacrebleu --tokenize ja-mecab.
Final pair-specialist screenshot replaced with genuine browser viewport media/browser/browser-0003.png (1280x1450,scroll60), resized to1130x1280 final.png. Read only final.png this turn. All requested model-card facts visible together; no visible dialogs.
