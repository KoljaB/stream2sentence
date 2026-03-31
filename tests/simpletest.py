from stream2sentence import generate_sentences

def generator():
    yield """No, the way it "cuts midway" is NOT like the audio is cut abruptly (like when you pause a video). You can check below the audio (sorry for not doing that earlier)"""

sentences = list(generate_sentences(generator(), minimum_sentence_length = 3, context_size=5, minimum_first_fragment_length = 3, quick_yield_single_sentence_fragment=True, debug=True))
print(sentences)