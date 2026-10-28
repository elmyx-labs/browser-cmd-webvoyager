Repository: https://github.com/google-research/BERT
Words: “Latest commit”; “Commit eedf571”; default “master branch”.
Commit: https://github.com/google-research/bert/commit/eedf5716ce1268e56f0a50264a88cafad334ac61
Words: “jacobdevlin-google authored Mar 11, 2020”; “Merge pull request #1027 from iuliaturc-google/master”; “Add links to 24 smaller BERT models.”; “1 file changed”; “71 additions & 0 deletions”; README.md.
Full diff read using browser-cmd text: 71 added lines at README lines 3–73; model release notice, explanation, download table, GLUE scores, hyperparameters, paper citation and 25 link definitions.

Verified directly again with browser-cmd text on the commit page:
README lines 13–20: columns H=128, H=256, H=512, H=768; rows L=2, L=4, L=6, L=8, L=10, L=12, with all 24 download links. Names: BERT-Tiny = 2/128; BERT-Mini = 4/256; BERT-Small = 4/512; BERT-Medium = 8/512; BERT-Base = 12/768.
README line 22: “Note that the BERT-Base model in this release is included for completeness only; it was re-trained under the same regime as the original model.”
README lines 24–31: “Here are the corresponding GLUE scores on the test set”. Columns Model|Score|CoLA|SST-2|MRPC|STS-B|QQP|MNLI-m|MNLI-mm|QNLI(v2)|RTE|WNLI|AX.
BERT-Tiny|64.2|0.0|83.2|81.1/71.1|74.3/73.6|62.2/83.4|70.2|70.3|81.5|57.2|62.3|21.0
BERT-Mini|65.8|0.0|85.9|81.1/71.8|75.4/73.3|66.4/86.2|74.8|74.3|84.1|57.9|62.3|26.1
BERT-Small|71.2|27.8|89.7|83.4/76.2|78.8/77.0|68.1/87.0|77.6|77.0|86.4|61.8|62.3|28.6
BERT-Medium|73.5|38.0|89.6|86.6/81.6|80.4/78.4|69.6/87.9|80.0|79.1|87.7|62.2|62.3|30.5
README lines 33–35: “For each task, we selected the best fine-tuning hyperparameters from the lists below, and trained for 4 epochs:” followed by “batch sizes: 8, 16, 32, 64, 128” and “learning rates: 3e-4, 1e-4, 5e-5, 3e-5”.
Source for all details: https://github.com/google-research/bert/commit/eedf5716ce1268e56f0a50264a88cafad334ac61
