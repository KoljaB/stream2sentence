from stream2sentence import generate_sentences
from openai import OpenAI                   # pip install openai

client = OpenAI()

def write(prompt: str):
    stream = client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "A three-sentence relaxing speech."}],
        stream=True,
    )
    for chunk in stream:
        if (text_chunk := chunk.choices[0].delta.content):
            yield text_chunk


text_stream = write("A three-sentence relaxing speech.")

for idx, sentence in enumerate(generate_sentences(text_stream), start=1):
    print(f"Sentence {idx}: {sentence}")


# stream = client.chat.completions.create(
#     model="gpt-4",
#     messages=[{"role": "user", "content": "A three-sentence relaxing speech."}],
#     stream=True,
# )

# TextToAudioStream(CoquiEngine(), log_characters=True).feed(stream).play()


# import os

# # openai.api_key = os.environ.get("OPENAI_API_KEY")

# def write(prompt: str):
#     for chunk in openai.ChatCompletion.create(
#         model="gpt-3.5-turbo",
#         messages=[{"role": "user", "content" : prompt}],
#         stream=True
#     ):
#         if (text_chunk := chunk["choices"][0]["delta"].get("content")) is not None:
#             yield text_chunk

# text_stream = write("A three-sentence relaxing speech.")

# for idx, sentence in enumerate(generate_sentences(text_stream), start=1):
#     print(f"Sentence {idx}: {sentence}")
