# ai-generated: 85% - Claude Code wrote the script from HANDOUT.md Stretch 1, reviewed by the student
"""Lab 3 Stretch 1 (M-28): one instrumented LLM call, its spans written as OTLP JSON to genai/spans.json.

Run (Ollama on an OpenAI-compatible endpoint):
    OPENAI_BASE_URL=http://localhost:11434/v1 OPENAI_API_KEY=ollama python genai/call_llm.py
"""
import os
import pathlib

from openai import OpenAI
from opentelemetry import trace
from opentelemetry.exporter.otlp.json.file import FileSpanExporter
from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

OUT = pathlib.Path(__file__).with_name("spans.json")
MODEL = os.environ.get("LLM_MODEL", "qwen3:0.6b")

provider = TracerProvider(resource=Resource.create({"service.name": "svcdesk-genai"}))
provider.add_span_processor(SimpleSpanProcessor(FileSpanExporter(str(OUT))))
trace.set_tracer_provider(provider)
OpenAIInstrumentor().instrument()

client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL", "http://localhost:11434/v1"),
                api_key=os.environ.get("OPENAI_API_KEY", "ollama"))
answer = client.chat.completions.create(
    model=MODEL,
    messages=[{"role": "user", "content": "In one sentence: what is a known error in ITIL? /no_think"}],
    max_tokens=80,
    temperature=0.2,
)
print(answer.choices[0].message.content)
provider.shutdown()
