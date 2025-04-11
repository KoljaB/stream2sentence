
from stream2sentence.stream2sentence_time_based import generate_sentences_time_based as generate_sentences
import time

input_stewart_wiki = '''
In 1996 Mr. Stewart hosted a short-lived talk show entitled, Where's Elvis This Week?, which was a half-hour, weekly comedy television program. 
It aired on Sunday nights in the United Kingdom on BBC Two. 
It was filmed at the CBS Broadcast Center in New York City and featured a set of panelists, two from the UK and two from the United States, who discussed news items and cultural issues. 
The show premiered in the UK on October 6, 1996; five episodes aired in total. 
Notable panelists included Dave Chappelle, Eddie Izzard, Phill Jupitus, Nora Ephron, Craig Kilborn, Christopher Hitchens, Armando Iannucci, Norm Macdonald, and Helen Gurley Brown. In 1997, Stewart was chosen as the host and interviewer for George Carlin's tenth HBO special, George Carlin: 40 Years of Comedy. 
Stewart had a recurring role in The Larry Sanders Show, playing himself as an occasional substitute and possible successor to late-night talk show host Larry Sanders (played by Garry Shandling). 
Stewart also headlined the 1997 White House Correspondents' dinner.
'''

input_problematic = ''' 
First sentence is short. 
Second sentence is very long, and totally a run on, and would definitely cause problems if this is what the output of the llm was and we only had a quick yield value of one this needs to be broken up thanks.
Third sentence also very long that lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Fourth sentence also very long fourth sentence that Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Fifth sentence also long Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
'''

WORDS_PER_TOKEN = .75

def get_words(current_input):
    return list(map(lambda word: word + ' ', current_input.split()))


def print_word_targets(current_input, tps_target):
    target_delay_between_words = (1 / (WORDS_PER_TOKEN * tps_target))
    word_targets = []
    for i, word in enumerate(get_words(current_input)):
        t = ((i + 1) * target_delay_between_words) + target_delay_between_words
        word_targets.append([ word, f"{t:.1f}" ])
    print(word_targets)


def get_llm_output_simulation(current_input, tts):
    def llm_output_simulation():
        for word in get_words(current_input):
            time.sleep(1 / (tts * WORDS_PER_TOKEN))
            yield word
    return llm_output_simulation()


def run_test(input, simulated_tts, dynamic_offset=False):
  time_to_sentences = []
  start_time = time.time()
  for i, sentence in enumerate(
    generate_sentences(
        get_llm_output_simulation(input, simulated_tts),
        deadline_offsets_dynamic=[.5, .3, .1] if dynamic_offset else [0]
    )):
        t = time.time() - start_time
        print(f"Sentence {i}: t={t:.1f} {sentence}")
        time_to_sentences.append([sentence, f"{t:.1f}"])
  print("\n\n RESULT ")
  print(time_to_sentences)
  print("\n\n")
  return time_to_sentences

def is_within_tolerance(num1, num2, tolerance):
    return abs(num1 - num2) <= tolerance

def compare_results(result, expected_result):
    for i in range(len(result)):
        if expected_result[i][0] != result[i][0] or not is_within_tolerance(float(expected_result[i][1]), float(result[i][1]), 0.25):
            raise ValueError(f"RESULT MISMATCH - expected={expected_result[i]} - actual={result[i]}")


result_1 = run_test(input_stewart_wiki, 9, True)
expected_result_1 = [
    ['In 1996 Mr. Stewart hosted a short-lived talk show entitled,', '1.8'],
    ["Where's Elvis This Week?, which was a half-hour,", '2.8'],
    ['weekly comedy television program.', '5.2'],
    ['It aired on Sunday nights in the United Kingdom on BBC Two.', '6.8'],
    ['It was filmed at the CBS Broadcast Center in New York City and featured a set of panelists, two from the UK and two from the United States,', '9.3'],
    ['who discussed news items and cultural issues.', '12.6'],
    ['The show premiered in the UK on October 6, 1996; five episodes aired in total.', '16.1'],
    ['Notable panelists included Dave Chappelle, Eddie Izzard, Phill Jupitus, Nora Ephron, Craig Kilborn, Christopher Hitchens, Armando Iannucci, Norm Macdonald, and Helen Gurley Brown.', '19.3'],
    ["In 1997, Stewart was chosen as the host and interviewer for George Carlin's tenth HBO special, George Carlin: 40 Years of Comedy.", '23.8'],
    ['Stewart had a recurring role in The Larry Sanders Show, playing himself as an occasional substitute and possible successor to late-night talk show host Larry Sanders (played by Garry Shandling).', '24.9'],
    ["Stewart also headlined the 1997 White House Correspondents' dinner.", '24.9']
]
compare_results(result_1, expected_result_1)

result_2 = run_test(input_stewart_wiki, 5)
expected_result_2 = [
    ['In 1996 Mr. Stewart hosted a short-lived talk show entitled,', '3.0'],
    ["Where's Elvis This Week?, which was a half-hour,", '5.4'],
    ['weekly comedy television program.', '8.0'],
    ['It aired on Sunday nights in the United Kingdom on BBC Two.', '9.4'],
    ['It was filmed at the CBS Broadcast Center in New York City and featured a set', '13.4'],
    ['of panelists, two from the UK and two from the United States, who discussed news items and cultural issues.', '18.8'],
    ['The show premiered in the UK on October 6, 1996; five episodes aired in total.', '25.1'],
    ['Notable panelists included Dave Chappelle, Eddie Izzard, Phill Jupitus, Nora Ephron, Craig Kilborn, Christopher Hitchens, Armando Iannucci, Norm Macdonald, and Helen Gurley Brown.', '30.0'],
    ["In 1997, Stewart was chosen as the host and interviewer for George Carlin's tenth HBO special, George Carlin: 40 Years of Comedy.", '37.7'],
    ['Stewart had a recurring role in The Larry Sanders Show, playing himself as an occasional substitute and possible successor to late-night talk show host Larry Sanders (played by Garry Shandling).', '44.9'],
    ["Stewart also headlined the 1997 White House Correspondents' dinner.", '44.9']
]
compare_results(result_2, expected_result_2)

result_3 = run_test(input_problematic, 9)
expected_result_3 = [
    ['First sentence is short.', '1.0'],
    ['Second sentence is very long,', '1.5'],
    ['and totally a run on,', '3.1'],
    ['and would definitely cause problems if this is what the output of the llm was and we only had a quick', '5.2'],
    ['yield value of one this needs to be broken up thanks.', '11.7'],
    ['Third sentence also very long that lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '15.3'],
    ['Fourth sentence also very long fourth sentence that Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '25.0'],
    ['Fifth sentence also long Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.', '25.0']
]
compare_results(result_3, expected_result_3)

result_4 = run_test(input_problematic, 5, True)
expected_result_4 = [
    ['First sentence is short.', '1.3'],
    ['Second sentence is very long,', '2.7'],
    ['and totally a run on,', '4.0'],
    ['and would definitely cause problems if this is what the output', '6.7'],
    ['of the llm was and we only had a quick', '9.4'],
    ['yield value of one this needs to be broken', '11.8'],
    ['up thanks. Third sentence also very long that lorem', '14.2'],
    ['ipsum dolor sit amet, consectetur adipiscing elit,', '17.4'],
    ['sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim', '19.5'],
    ['ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '23.5'],
    ['Fourth sentence also very long fourth sentence that Lorem ipsum dolor sit amet, consectetur adipiscing elit,', '28.3'],
    ['sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam,', '33.6'],
    ['quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '39.3'],
    ['Fifth sentence also long Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat non', '42.0'],
    ['proident, sunt in culpa qui officia deserunt mollit anim id est laborum.', '45.2']
]
compare_results(result_4, expected_result_4)
