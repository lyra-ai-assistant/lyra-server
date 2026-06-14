import sys

_MB_PER_TOKEN = 2.0
_SYSTEM_RESERVE_MB = 512
_MIN_TOKENS = 64
_MAX_TOKENS = 1024


def compute_max_tokens() -> int:
    if sys.platform != "linux":
        return _MAX_TOKENS

    with open("/proc/meminfo") as f:
        data = {
            k.strip(): int(v.split()[0])
            for line in f
            if ":" in line
            for k, v in [line.split(":", 1)]
        }

    available_mb = data.get("MemAvailable", 0) / 1024
    budget_mb = max(0, available_mb - _SYSTEM_RESERVE_MB)
    tokens = int(budget_mb / _MB_PER_TOKEN)

    return max(_MIN_TOKENS, min(tokens, _MAX_TOKENS))
