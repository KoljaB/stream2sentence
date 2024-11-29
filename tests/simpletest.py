from stream2sentence import generate_sentences

def generator():
    yield "Hallo, "
    yield "wie geht es dir? "
    yield "Mir geht es gut."
expected = ["Hallo,", "wie geht es dir?", "Mir geht es gut."]
sentences = list(generate_sentences(generator(), minimum_sentence_length = 3, context_size=5, minimum_first_fragment_length = 3, quick_yield_single_sentence_fragment=True))

print(sentences)