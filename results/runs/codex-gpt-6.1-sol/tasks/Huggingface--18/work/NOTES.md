Verified in browser: https://github.com/huggingface/trl/blob/v0.12.1/docs/source/reward_trainer.mdx
Reward Modeling → Adding a margin to the loss.
Exact documentation: “As in the Llama 2 paper, you can add a margin to the loss by adding a margin column to the dataset. The reward collator will automatically pass it through and the loss will be computed accordingly.”
Code: def add_margin(row): return {'margin': row['score_chosen'] - row['score_rejected']}; dataset = dataset.map(add_margin)
Hugging Face currently returns HTTP 429 for versioned Reward Modeling pages and the current main page. Clean retry returned the same result. Initial current main Reward Modeling page was readable, but only contained margin as a logged metric.
Resolved: Hugging Face became readable again. Selected v0.12.2 using the documentation version selector and opened the section. Browser text directly confirmed the same instructions and code at https://huggingface.co/docs/trl/v0.12.2/en/reward_trainer#adding-a-margin-to-the-loss . Captured this viewport, resized with sips to final.png (long side 1280), and read only final.png. No overlay covers the relevant evidence.
