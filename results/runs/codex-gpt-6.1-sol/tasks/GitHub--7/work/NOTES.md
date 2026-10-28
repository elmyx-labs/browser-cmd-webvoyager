Official source: Google Research blog, December 20, 2019: https://research.google/blog/albert-a-lite-bert-for-self-supervised-learning-of-language-representations/
“ALBERT is being released as an open-source implementation on top of TensorFlow” — the “released” and “open-sourcing ALBERT” links point to https://github.com/google-research/ALBERT, verified through browser-cmd eval.
Repository homepage (browser-cmd pages): default branch master; Latest commit b772393, Apr 12, 2023, “Replace deprecated tf.contrib.data.map_and_batch(...) with `tf.data…”.
Latest commit detail: https://github.com/google-research/albert/commit/b772393d3dae115b493258ce8e37c17b2cc62100
Browser page states: “Commit b772393”; “albert-copybara committed Apr 12, 2023”; “2 files changed”; “2 additions & 4 deletions”. File tree: classifier_utils.py and squad_utils.py. Each file has +1 / -2. Both remove the contrib_data import and replace contrib_data.map_and_batch with tf.data.experimental.map_and_batch.
