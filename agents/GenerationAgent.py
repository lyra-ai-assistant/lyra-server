from pathlib import Path
from threading import Thread
from transformers import pipeline, TextIteratorStreamer
from typing import Generator

from util.gpu import get_device_config
from util.formatting import clean_response

MODEL_ID = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
_PROMPT_FILE = Path(__file__).parent.parent / "templates" / "system_prompt.txt"

_GENERATION_KWARGS = dict(
    max_new_tokens=1024,
    do_sample=True,
    temperature=0.7,
    top_k=50,
    top_p=0.95,
)


class GenerationAgent:
    def __init__(self):
        cfg = get_device_config()
        self.pipe = pipeline(
            "text-generation",
            model=MODEL_ID,
            torch_dtype=cfg["torch_dtype"],
            device_map=cfg["device_map"] if cfg["device_map"] else cfg["device"],
        )
        self._system_prompt = _PROMPT_FILE.read_text(encoding="utf-8").strip()

    def warmup(self) -> None:
        """Run a minimal inference to pre-warm model caches before serving requests."""
        self.pipe("Hi", max_new_tokens=1, do_sample=False)

    def handle_request(
        self,
        text: str,
        history: list | None = None,
        semantic_ctx: list[str] | None = None,
        knowledge_ctx: list[str] | None = None,
    ) -> str:
        prompt = self._build_prompt(text, history, semantic_ctx, knowledge_ctx)
        output = self.pipe(prompt, **_GENERATION_KWARGS)
        raw: str = output[0]["generated_text"]
        return self._extract_reply(raw)

    def stream_request(
        self,
        text: str,
        history: list | None = None,
        semantic_ctx: list[str] | None = None,
        knowledge_ctx: list[str] | None = None,
    ) -> Generator[str, None, None]:
        prompt = self._build_prompt(text, history, semantic_ctx, knowledge_ctx)
        streamer = TextIteratorStreamer(
            self.pipe.tokenizer, skip_prompt=True, skip_special_tokens=True
        )
        device = next(self.pipe.model.parameters()).device
        inputs = self.pipe.tokenizer(prompt, return_tensors="pt").to(device)

        thread = Thread(
            target=self.pipe.model.generate,
            kwargs={**inputs, "streamer": streamer, **_GENERATION_KWARGS},
            daemon=True,
        )
        thread.start()

        for token in streamer:
            yield token

    # -- private --

    def _build_prompt(
        self,
        text: str,
        history: list | None,
        semantic_ctx: list[str] | None,
        knowledge_ctx: list[str] | None,
    ) -> str:
        messages = self._build_messages(text, history, semantic_ctx, knowledge_ctx)
        return self.pipe.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    def _build_messages(
        self,
        text: str,
        history: list | None,
        semantic_ctx: list[str] | None,
        knowledge_ctx: list[str] | None,
    ) -> list:
        system = self._system_prompt
        if knowledge_ctx:
            joined = "\n---\n".join(knowledge_ctx)
            system += f"\n\nRelevant Ubuntu package information:\n{joined}"
        if semantic_ctx:
            joined = "\n---\n".join(semantic_ctx)
            system += f"\n\nRelevant context from past conversations:\n{joined}"

        messages = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": text})
        return messages

    def _extract_reply(self, raw: str) -> str:
        marker = "<|assistant|>"
        if marker in raw:
            raw = raw.split(marker)[-1]
        return clean_response(raw)
