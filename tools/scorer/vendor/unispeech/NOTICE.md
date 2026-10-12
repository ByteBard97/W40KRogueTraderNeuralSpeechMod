Vendored, minimal, for local speaker-similarity scoring.
- WavLM.py, modules.py: Microsoft WavLM (MIT), via s3prl/upstream/wavlm (github.com/s3prl/s3prl), unmodified.
- ecapa_tdnn.py: microsoft/UniSpeech downstreams/speaker_verification/models/ecapa_tdnn.py, only change: the
  fairseq/s3prl `UpstreamExpert` import is stubbed out (see sv_model.py).
- Weights (not in repo): wavlm_large_finetune.pth, UniSpeech WavLM-large+ECAPA-TDNN SV, CC BY-SA 3.0 per the
  UniSpeech repo. Downloaded from HF mirror bezzam/wavlm_large_finetune_seed_tts_eval (sha256 51f07e3b...).
