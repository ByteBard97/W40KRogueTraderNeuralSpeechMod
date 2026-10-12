"""WavLM-large + ECAPA-TDNN speaker verification (UniSpeech / seed-tts-eval SIM-o), no fairseq/s3prl."""
import torch
import torch.nn.functional as F
from .WavLM import WavLM, WavLMConfig
from .ecapa_tdnn import ECAPA_TDNN

WAVLM_LARGE_CFG = dict(
    extractor_mode="layer_norm", encoder_layers=24, encoder_embed_dim=1024,
    encoder_ffn_embed_dim=4096, encoder_attention_heads=16, layer_norm_first=True,
    normalize=True, conv_bias=False, relative_position_embedding=True,
    num_buckets=320, max_distance=800, gru_rel_pos=True,
    dropout=0.0, attention_dropout=0.0, activation_dropout=0.0)


class WavLMFeat(torch.nn.Module):
    """Mimics s3prl wavlm UpstreamExpert hooks: 24 layer inputs + encoder output, each B x T x C."""
    def __init__(self):
        super().__init__()
        self.cfg = WavLMConfig(WAVLM_LARGE_CFG)
        self.model = WavLM(self.cfg)
        self.model.feature_grad_mult = 0.0
        self.model.encoder.layerdrop = 0.0
        self._h = []
        for layer in self.model.encoder.layers:
            layer.register_forward_hook(lambda m, i, o: self._h.append(i[0].transpose(0, 1)))
        self.model.encoder.register_forward_hook(lambda m, i, o: self._h.append(o[0]))

    def forward(self, wavs):
        wavs = [F.layer_norm(w, w.shape) for w in wavs]
        x = torch.nn.utils.rnn.pad_sequence(wavs, batch_first=True)
        self._h = []
        self.model.extract_features(x, padding_mask=torch.zeros_like(x, dtype=torch.bool), mask=False)
        h, self._h = self._h, []
        return {"hidden_states": h}


class SVModel(ECAPA_TDNN):
    def __init__(self):
        torch.nn.Module.__init__(self)
        # build ECAPA_TDNN with a stub extractor, then swap in WavLM
        import types
        ECAPA_TDNN.__init__.__globals__["UpstreamExpert"] = None
        super_init = ECAPA_TDNN.__init__
        # feat_type != fbank/mfcc path calls torch.hub; avoid by constructing with fbank then patching
        super_init(self, feat_dim=1024, channels=512, emb_dim=256, feat_type="fbank")
        self.feat_type = "wavlm_large"
        self.feature_selection = "hidden_states"
        self.update_extract = False
        self.feature_extract = WavLMFeat()
        self.feature_weight = torch.nn.Parameter(torch.zeros(25))
        self.instance_norm = torch.nn.InstanceNorm1d(1024)
        self.layer1 = type(self.layer1)(1024, 512, kernel_size=5, padding=2)


def load_sv(ckpt_path, device="cpu"):
    m = SVModel()
    sd = torch.load(ckpt_path, map_location="cpu")["model"]
    res = m.load_state_dict(sd, strict=False)
    bad_missing = [k for k in res.missing_keys if "num_batches" not in k]
    bad_unexp = [k for k in res.unexpected_keys if not k.startswith("loss_calculator")]
    if bad_missing or bad_unexp:
        raise RuntimeError(f"state dict mismatch: missing={bad_missing[:8]} unexpected={bad_unexp[:8]}")
    return m.eval().to(device)


@torch.no_grad()
def embed(model, wav16k_mono, device="cpu"):
    e = model(wav16k_mono.float().unsqueeze(0).to(device))
    return F.normalize(e, dim=-1)[0].cpu()
