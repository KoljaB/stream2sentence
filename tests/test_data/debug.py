
'''
Run this script to replay actual tokens on a configuration of your choice
'''

from stream2sentence.stream2sentence_time_based import generate_sentences
import time

records = []
buffer = ""
with open("1.txt", "r") as f:
    for line in f:
        #include newlines in split
        if "!@#" in line:
            buffer += line
            records.append(buffer)
            buffer = ""
        else:
            buffer += line
    if buffer:
        records.append(buffer)

token_times = [tuple(record.split("!@#", 1)) for record in records]



def get_llm_output_simulation():
    start = time.time()
    def llm_output_simulation():
        for tt in token_times:
            # print(tt)
            while (time.time() - start) < float(tt[1]):
                time.sleep(0.0001)
            yield tt[0]

    return llm_output_simulation()


def run_test():
  time_to_sentences = []
  start_time = time.time()
  for i, sentence in enumerate(
    generate_sentences(
        get_llm_output_simulation(),
        lead_time = 0.3,
        max_wait_for_fragments = [1, 0.8, 1, 1.1, 1.5],
        target_tps = 3.6,
        min_output_lengths = [2, 3],
        deadline_offsets_dynamic=[.1]
    )):
        t = time.time() - start_time
        print(f"Sentence {i}: t={t:.1f} {sentence}")
        time_to_sentences.append([sentence, f"{t:.1f}"])
  return time_to_sentences


run_test()