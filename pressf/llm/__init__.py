from .client import LLMClient


def build_llm_client(cfg):
    """Judge factory by llm.provider from lazy.yaml. All clients implement
    one protocol parse()/count_tokens() - the judge does not know who is under it."""
    provider = getattr(cfg, "provider", "anthropic")
    if provider == "anthropic":
        return LLMClient()
    if provider == "openai":
        from .openai_client import OpenAILLMClient

        return OpenAILLMClient()
    if provider == "openai_compatible":
        import os

        from .openai_client import OpenAILLMClient

        if not cfg.base_url:
            raise ValueError(
                "provider=openai_compatible requires llm.base_url in lazy.yaml"
                "(for example http://localhost:11434/v1 for Ollama)"
            )
        #local servers do not need a key, but SDK requires a non-empty one
        api_key = os.environ.get("OPENAI_COMPAT_API_KEY") or os.environ.get("OPENAI_API_KEY") or "not-needed"
        return OpenAILLMClient(
            base_url=cfg.base_url,
            api_key=api_key,
            price_per_mtok=(cfg.price_input_per_mtok, cfg.price_output_per_mtok),
            schema_fallback=True,
        )
    raise ValueError(
        f"Unknown llm.provider:{provider}. Available: anthropic, openai, openai_compatible"
    )


__all__ = ["LLMClient", "build_llm_client"]
