import torch


def get_device_config() -> dict:
    """Return device string, torch dtype, and device_map for pipeline initialization."""
    if torch.cuda.is_available():
        return {"device": "cuda", "torch_dtype": torch.bfloat16, "device_map": "auto"}
    return {"device": "cpu", "torch_dtype": torch.float32, "device_map": None}
