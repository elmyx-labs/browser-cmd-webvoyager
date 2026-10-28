Hugging Face Transformers documentation was reached from https://huggingface.co/ via Docs > Transformers > documentation search "add_tokens".
The selected documentation version is v5.21.0; language EN.
Source: https://huggingface.co/docs/transformers/v5.21.0/main_classes/tokenizer#transformers.PythonBackend.add_tokens
Exact words: "Tokens are only added if they are not already in the vocabulary."
Exact words: "Number of tokens added to the vocabulary."
Exact words: "If the new tokens are not in the vocabulary, they are added to the end."
Signature: add_tokens(new_tokens: str | AddedToken | Sequence[str | AddedToken], special_tokens: bool = False) -> int.
Example: num_added_toks = tokenizer.add_tokens(["new_tok1", "my_new-tok2"])
Exact words: "resize_token_embeddings expect to receive the full size of the new vocabulary, i.e., the length of the tokenizer."
Example: model.resize_token_embeddings(len(tokenizer))
Source: https://huggingface.co/docs/transformers/v5.21.0/main_classes/tokenizer#transformers.PythonBackend.add_special_tokens
Exact words: "Add a dictionary of special tokens (eos, pad, cls, etc.) to the encoder and link them to class attributes."
Example: special_tokens_dict = {"cls_token": "<CLS>"}; tokenizer.add_special_tokens(special_tokens_dict)
Exact words: "Special tokens can be skipped when decoding using skip_special_tokens = True."

Verified directly in the browser: https://huggingface.co/docs/transformers/v5.21.0/main_classes/tokenizer#transformers.PythonBackend.add_special_tokens
Exact words: "Special tokens are carefully handled by the tokenizer (they are never split), similar to AddedTokens."
The final viewport includes this sentence, add_special_tokens, skip_special_tokens = True, and the preceding add_tokens example with model.resize_token_embeddings(len(tokenizer)).
