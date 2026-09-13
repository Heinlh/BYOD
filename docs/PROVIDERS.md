# Provider contracts

BYOD implements the specification's
[OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create),
[Anthropic Messages streaming](https://platform.claude.com/docs/en/build-with-claude/streaming),
and [Ollama chat](https://docs.ollama.com/api/chat) protocols over one HTTPX transport.
Cloud API destinations are fixed; redirects and environment proxies are disabled.
API keys are validated with a minimal completion before OS-keychain persistence.

Model lists come from the configured provider. Unselected cloud providers use
static fallback labels without a network call; selecting/configuring them enables
their model-list request. Ollama detection is limited to localhost:11434.

OpenAI requests disable server-side completion storage. No provider embedding
endpoint is used. Raw provider errors are never returned to the UI or logged.

The live development gate uses the existing local Ollama model. Cloud provider
wire tests use mocked LLM responses; live OpenAI/Anthropic validation requires
the user's own credentials saved through the OS keychain.
