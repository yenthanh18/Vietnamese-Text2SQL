"""Explicit model lifecycle; importing this module never imports ML libraries."""

import json
from functools import lru_cache
from threading import RLock

from backend.config import PROJECT_ROOT, Settings, get_settings


class ModelNotLoadedError(RuntimeError):
    pass


class ModelRuntime:
    def __init__(self, settings: Settings | None = None):
        settings = settings or get_settings()
        self.device = settings.model_device
        self.base_model = settings.base_model
        self.adapter_path = (PROJECT_ROOT / settings.adapter_path).resolve()
        self.tokenizer = None
        self.model = None
        self._lock = RLock()

    @property
    def model_loaded(self) -> bool:
        return self.model is not None and self.tokenizer is not None

    def get_status(self) -> dict:
        return {
            "model_loaded": self.model_loaded,
            "device": self.device,
            "base_model": self.base_model,
            "adapter_path": str(self.adapter_path),
        }

    def require_loaded(self):
        if not self.model_loaded:
            raise ModelNotLoadedError(
                "Model chưa được tải. Cần gọi ModelRuntime.load_model() một cách "
                "tường minh trên máy inference trước khi sinh SQL."
            )
        return self.tokenizer, self.model

    def load_model(self, *, use_4bit: bool = False) -> None:
        """Only an explicit Python call may download/load weights; no API calls this."""
        with self._lock:
            if self.model_loaded:
                return
            if use_4bit and not self.device.startswith("cuda"):
                raise ValueError("4-bit quantization chỉ được bật với MODEL_DEVICE=cuda.")
            for filename in ("adapter_config.json", "adapter_model.safetensors"):
                if not (self.adapter_path / filename).is_file():
                    raise FileNotFoundError(f"Thiếu adapter artifact: {filename}")
            config = json.loads(
                (self.adapter_path / "adapter_config.json").read_text(encoding="utf-8")
            )
            if config.get("base_model_name_or_path") != self.base_model:
                raise ValueError("BASE_MODEL không khớp base model của adapter đã huấn luyện.")
            try:
                import torch
                from peft import PeftModel
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                raise RuntimeError(
                    "Thiếu dependencies inference. Cài backend/requirements.txt trước khi tải model."
                ) from exc

            device = torch.device(self.device)
            if device.type == "cuda":
                if not torch.cuda.is_available():
                    raise RuntimeError("MODEL_DEVICE yêu cầu CUDA nhưng CUDA không khả dụng.")
                if device.index is not None and device.index >= torch.cuda.device_count():
                    raise ValueError("MODEL_DEVICE trỏ đến GPU không tồn tại.")
            kwargs = {
                "device_map": {"": self.device},
                "torch_dtype": torch.float32 if device.type == "cpu" else torch.float16,
            }
            if use_4bit:
                try:
                    import bitsandbytes  # noqa: F401 -- optional CUDA dependency
                except ImportError as exc:
                    raise RuntimeError("CUDA 4-bit cần cài thêm bitsandbytes.") from exc
                from transformers import BitsAndBytesConfig

                kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.float16,
                )
            # Use the tokenizer/chat template saved with the trained adapter.
            tokenizer = AutoTokenizer.from_pretrained(
                str(self.adapter_path), local_files_only=True,
            )
            base = AutoModelForCausalLM.from_pretrained(self.base_model, **kwargs)
            model = PeftModel.from_pretrained(
                base, str(self.adapter_path), is_trainable=False, local_files_only=True,
            )
            model.eval()
            # Publish references only after every loading step succeeds.
            self.tokenizer, self.model = tokenizer, model


@lru_cache
def get_model_runtime() -> ModelRuntime:
    return ModelRuntime()
