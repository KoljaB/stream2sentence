from stream2sentence import generate_sentences

def dummy_generator():
    yield "This is a sentence. And here's another! Yet, "
    yield "there's more. This ends now."

for idx, sentence in enumerate(generate_sentences(dummy_generator()), start=1):
    print(f"Sentence {idx}: {sentence}")