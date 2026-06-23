from stream2sentence import generate_sentences
import os
import unittest

try:
    from openai import OpenAI                   # pip install openai
except ImportError as exc:
    raise unittest.SkipTest("openai package is required for live LLM stream tests") from exc

if not os.environ.get("OPENAI_API_KEY"):
    raise unittest.SkipTest("OPENAI_API_KEY is required for live LLM stream tests")

client = OpenAI()

def write(prompt: str):
    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        if (text_chunk := chunk.choices[0].delta.content):
            yield text_chunk


text_stream = write("A three-sentence relaxing speech.")

for idx, sentence in enumerate(generate_sentences(text_stream, minimum_sentence_length=5), start=1):
    print(f"Sentence {idx}: {sentence}")
