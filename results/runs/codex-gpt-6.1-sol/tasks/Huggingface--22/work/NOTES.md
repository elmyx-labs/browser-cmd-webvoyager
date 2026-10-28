Source: https://huggingface.co/transformers/v4.12.0/quicktour.html#using-the-model
Title: Quick tour — transformers 4.12.0 documentation
Section: Under the hood: pretrained models > Using the model
Exact evidence:
"Once your model is fine-tuned, you can save it with its tokenizer in the following way:"
tokenizer.save_pretrained(save_directory)
model.save_pretrained(save_directory)
"If you are loading a saved PyTorch model in a TensorFlow model, use from_pretrained() like this:"
from transformers import TFAutoModel
tokenizer = AutoTokenizer.from_pretrained(save_directory)
model = TFAutoModel.from_pretrained(save_directory, from_pt=True)
