import sys
import os
from types import SimpleNamespace
import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
import veil.run as run


def test_run_video_only_without_optional_imports(monkeypatch):
    """Ensure video-only execution doesn't import optional heavy deps."""
    # Ensure optional modules not pre-imported
    monkeypatch.delitem(sys.modules, 'veil.audio_whisper', raising=False)
    monkeypatch.delitem(sys.modules, 'veil.fusion.yamnet_events', raising=False)

    # Minimal label loader returning one prompt
    monkeypatch.setattr(
        run, 'load_master_labels', lambda *a, **k: SimpleNamespace(video_labels=['a video about cat'], photo_labels=['a photo of cat'])
    )
    monkeypatch.setattr(run, 'select_labels', lambda master, mode: master.video_labels)

    # Dummy CLIP model and tokenizer
    class DummyModel(torch.nn.Module):
        def encode_text(self, tokens):
            return torch.ones((tokens.shape[0], 1))

        def encode_image(self, imgs):
            return torch.ones((imgs.shape[0], 1))

    monkeypatch.setattr(run, 'get_clip_model', lambda *a, **k: (DummyModel(), lambda x: torch.ones(3, 224, 224)))
    monkeypatch.setattr(run.clip, 'tokenize', lambda texts, truncate=True: torch.zeros((len(texts), 1), dtype=torch.int32))

    # Avoid reading actual video
    monkeypatch.setattr(
        run,
        'classify_video_clip',
        lambda *a, **k: {'scores': np.zeros(1), 'frame_count': 0}
    )

    # Run runner in video-only mode
    monkeypatch.setenv('PYTHONHASHSEED', '0')
    monkeypatch.setattr(
        sys,
        'argv',
        ['prog', '--mode', 'video', '--video', 'dummy.mp4', '--use_whisper', 'false', '--use_yamnet', 'false', '--topk', '1']
    )
    run.main()

    assert 'veil.audio_whisper' not in sys.modules
    assert 'veil.fusion.yamnet_events' not in sys.modules
