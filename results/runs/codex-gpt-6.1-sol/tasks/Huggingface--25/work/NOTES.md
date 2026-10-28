Source: https://huggingface.co/docs/transformers/peft (v5.21.0)
Title: Parameter-efficient fine-tuning; section: Loading an adapter.
Exact words: "For large models, load a quantized version in 8-bit or 4-bit precision with bitsandbytes to save memory. Add device_map=\"auto\" to distribute the model across available hardware."
Code uses AutoModelForCausalLM.from_pretrained with quantization_config=BitsAndBytesConfig(load_in_8bit=True), device_map="auto".
Adapter repository or directory must contain adapter_config.json and adapter weights; from_pretrained automatically reads base_model_name_or_path and loads the base model and adapter.
Source: https://huggingface.co/docs/transformers/v4.49.0/en/peft#load-in-8bit-or-4bit
Title: Load adapters with 🤗 PEFT; section: Load in 8bit or 4bit; version: v4.49.0.
Exact words: "The bitsandbytes integration supports 8bit and 4bit precision data types, which are useful for loading large models because it saves memory (see the bitsandbytes integration guide to learn more). Add the load_in_8bit or load_in_4bit parameters to from_pretrained() and set device_map=\"auto\" to effectively distribute the model to your hardware:"
Example: peft_model_id = "ybelkada/opt-350m-lora"; model = AutoModelForCausalLM.from_pretrained(peft_model_id, quantization_config=BitsAndBytesConfig(load_in_8bit=True)).
