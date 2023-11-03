from stream2sentence import generate_sentences
import openai                               # pip install openai  
import os

openai.api_key = os.environ.get("OPENAI_API_KEY")

def write(prompt: str):
    for chunk in openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content" : prompt}],
        stream=True
    ):
        if (text_chunk := chunk["choices"][0]["delta"].get("content")) is not None:
            yield text_chunk

text_stream = write("A three-sentence relaxing speech.")

for idx, sentence in enumerate(generate_sentences(text_stream), start=1):
    print(f"Sentence {idx}: {sentence}")
