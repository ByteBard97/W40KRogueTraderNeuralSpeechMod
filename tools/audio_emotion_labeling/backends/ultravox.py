"""Ultravox (Llama-3.1-8B + Whisper adapter) backend adapter."""
from __future__ import annotations

import librosa
import torch
from transformers import AutoModel, AutoModelForCausalLM, AutoProcessor, BitsAndBytesConfig

MODEL_ID = "fixie-ai/ultravox-v0_5-llama-3_1-8b"
REVISION = "94aa77f70ca548e669ea61f737e159b2fddbb7f7"
LLAMA_REVISION = "0e9e39f249a16976918f6564b8830bc894c89659"


def load_model():
    processor = AutoProcessor.from_pretrained(
        MODEL_ID, revision=REVISION, trust_remote_code=True)
    # Ultravox's own checkpoint is only ~1.3GB: it does NOT contain the Llama-3.1-8B backbone.
    # UltravoxModel.__init__ pulls that backbone in via its own internal
    # AutoModelForCausalLM.from_pretrained(config.text_model_id, ...) call, and the remote
    # code's SHARED_PRETRAINED_KWARGS allowlist (see cached ultravox_model.py) does NOT forward
    # `quantization_config` to that inner call. Passing quantization_config to the *outer*
    # AutoModel.from_pretrained(MODEL_ID, ...) instead triggers transformers 4.57.3 to quantize
    # the whole composite model post-hoc, which crashes in
    # transformers.modeling_utils.PreTrainedModel._initialize_missing_keys (reproduced: it
    # iterates self.state_dict(), which for a bnb Linear4bit layer includes compound keys like
    # "...q_proj.weight.absmax"; get_module_from_name() rsplits on the last ".", and
    # model.get_submodule("...q_proj.weight") then raises
    # AttributeError("`weight` is not an nn.Module") because `weight` is a leaf Params4bit, not
    # a submodule -- confirmed via full traceback and by patching _initialize_missing_keys to
    # print, both against the installed transformers==4.57.3 source, not just the docs).
    # A plain bf16 whole-model load with device_map="auto" also fails: the composite model
    # (~16GB Llama backbone + ~1-2GB Whisper encoder) doesn't fit in this GPU's free VRAM, and
    # accelerate's device_map="auto" dispatch produces unbacked meta-device tensors instead of
    # erroring at load time (NotImplementedError: "Cannot copy out of meta tensor; no data!" /
    # "weight is on the meta device, we need a `value`" -- reproduced with and without an
    # explicit max_memory/offload_folder).
    #
    # Workaround: build the composite model plainly on CPU in bf16 (no device_map -> no
    # accelerate dispatch hooks -> no meta-tensor path), which correctly loads Ultravox's real
    # finetuned audio_tower/multi_modal_projector plus a real (unquantized) language_model, then
    # swap `model.language_model` for a separately, cleanly 4-bit-quantized
    # AutoModelForCausalLM.from_pretrained(...) loaded straight onto the GPU, and move the small
    # audio tower/projector onto the GPU explicitly. This sidesteps both broken paths above
    # entirely rather than patching either of them.
    try:
        model = AutoModel.from_pretrained(
            MODEL_ID, revision=REVISION, trust_remote_code=True, dtype=torch.bfloat16)
        bnb_config = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16)
        # dtype=torch.bfloat16 here (not just bnb_4bit_compute_dtype, which only governs the
        # quantized-matmul compute dtype) matters: it keeps unquantized submodules -- notably
        # embed_tokens -- in bf16 instead of the fp32 bitsandbytes defaults them to otherwise.
        # ultravox_model.py's forward() casts the audio tower's output to inputs_embeds.dtype
        # (from this embedding layer) right before multi_modal_projector (bf16) consumes it;
        # an fp32 embed_tokens produced a dtype-mismatch RuntimeError there (reproduced without
        # this kwarg, both with and without an extra manual cast of `audio_values` in generate()
        # below -- the embedding dtype was the actual root cause, not audio_values itself).
        quantized_lm = AutoModelForCausalLM.from_pretrained(
            model.config.text_model_id, revision=LLAMA_REVISION,
            quantization_config=bnb_config, device_map={"": 0}, dtype=torch.bfloat16)
        model.language_model = quantized_lm
        model.audio_tower.to("cuda:0")
        model.multi_modal_projector.to("cuda:0")
        quant = "4bit-bnb"
    except Exception as e:  # noqa: BLE001 - bnb kernel support on this GPU is unverified
        print(f"4-bit load failed ({e}); falling back to bf16")
        # NOTE: a GPU-resident bf16 load of this model does not work on this hardware, in
        # either of its two forms -- both reproduced directly, not just inferred:
        #   1. device_map={"": 0} (single GPU, no offload): OOMs immediately at load time.
        #      Llama-3.1-8B-Instruct alone in bf16 is ~16GB, which already exceeds this card's
        #      ~13.7GB free VRAM before the Whisper encoder/projector are even added.
        #   2. device_map="auto" (real accelerate CPU offload, i.e. NOT the meta-tensor bug
        #      that broke the *composite* UltravoxModel's own device_map="auto" path above --
        #      this is a plain, native LlamaForCausalLM, so accelerate's offload hooks work
        #      correctly here): loads without error, but OOMs during generate() when an
        #      offloaded layer streams back onto the GPU
        #      (torch.OutOfMemoryError: "Tried to allocate 1002.00 MiB... 963.31 MiB is free").
        # So this fallback runs the whole composite model on CPU instead (no device_map at
        # all): slower (~13s/generation and a one-time ~100s build, measured on this machine,
        # vs. sub-second on the 4-bit GPU path), but it actually completes, unlike either
        # GPU-resident bf16 variant. `model.device` reports "cpu", so generate()'s existing
        # `.to(model.device)` on its inputs already does the right thing here unmodified.
        model = AutoModel.from_pretrained(
            MODEL_ID, revision=REVISION, trust_remote_code=True, dtype=torch.bfloat16)
        quant = "bf16-cpu"
    return model, processor, {"model_id": MODEL_ID, "quant": quant,
                               "temperature": 0.0, "max_new_tokens": 192}


def generate(model, processor, wav_path: str, prompt_text: str) -> str:
    audio, _ = librosa.load(wav_path, sr=16000, mono=True)
    # UltravoxProcessor.__call__ takes `text`/`audio`/`sampling_rate` — it has no `turns=`
    # kwarg (verified against the cached ultravox_processing.py). The `turns` shape from the
    # brief is what UltravoxPipeline.preprocess() accepts; that pipeline builds `text` itself
    # via apply_chat_template() and splices an "<|audio|>" placeholder into the last user turn
    # before calling the processor (see cached ultravox_pipeline.py). We replicate that here
    # since load_model()/generate() use AutoModel/AutoProcessor directly, not the pipeline.
    audio_prompt = prompt_text if "<|audio|>" in prompt_text else f"{prompt_text} <|audio|>"
    turns = [{"role": "system", "content": "You are an expert at judging vocal emotion."},
             {"role": "user", "content": audio_prompt}]
    text = processor.tokenizer.apply_chat_template(turns, add_generation_prompt=True, tokenize=False)
    inputs = processor(text=text, audio=audio, sampling_rate=16000, return_tensors="pt")
    inputs = {k: v.to(model.device) if hasattr(v, "to") else v for k, v in inputs.items()}
    generated = model.generate(**inputs, max_new_tokens=192, do_sample=False)
    generated = generated[:, inputs["input_ids"].shape[1]:]
    return processor.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
