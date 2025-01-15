
from stream2sentence.stream2sentence_time_based import generate_sentences
import time

input_stewart_wiki = '''
In 1996, Stewart hosted a short-lived talk show entitled, Where's Elvis This Week?, which was a half-hour, weekly comedy television program. 
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


def run_test(input, simulated_tts):
  time_to_sentences = []
  start_time = time.time()
  for i, sentence in enumerate(
    generate_sentences(
        get_llm_output_simulation(input, simulated_tts),
    )):
        t = time.time() - start_time
        print(f"Sentence {i}: t={t:.1f} {sentence}")
        time_to_sentences.append([sentence, f"{t:.1f}"])
  return time_to_sentences

def is_within_tolerance(num1, num2, tolerance):
    return abs(num1 - num2) <= tolerance

def compare_results(result, expected_result):
    for i in range(len(result)):
        if expected_result[i][0] != result[i][0] or not is_within_tolerance(float(expected_result[i][1]), float(result[i][1]), 0.2):
            raise ValueError(f"RESULT MISMATCH - expected={expected_result[i]} - actual={result[i]}")


result_1 = run_test(input_stewart_wiki, 9)
expected_result_1 = [
   ['In 1996, Stewart hosted a short-lived', '1.1'], 
   ["talk show entitled, Where's Elvis This Week?", '2.8'], 
   ['which was a half-hour, weekly comedy television program.', '5.3'], 
   ['It aired on Sunday nights in the United Kingdom on BBC Two.', '7.9'], 
   ['It was filmed at the CBS Broadcast Center in New York City and featured a set of panelists, two from the UK and two from the United States, who discussed news items and cultural issues.', '11.8'], 
   ['The show premiered in the UK on October 6, 1996; five episodes aired in total.', '16.6'], 
   ['Notable panelists included Dave Chappelle, Eddie Izzard, Phill Jupitus, Nora Ephron, Craig Kilborn, Christopher Hitchens, Armando Iannucci, Norm Macdonald, and Helen Gurley Brown.', '19.9'], 
   ["In 1997, Stewart was chosen as the host and interviewer for George Carlin's tenth HBO special, George Carlin: 40 Years of Comedy.", '24.5'], 
   [' Stewart had a recurring role in The Larry Sanders Show, playing himself as an occasional substitute and possible successor to late-night talk show host Larry Sanders (played by Garry Shandling).', '25.6'], 
   ["Stewart also headlined the 1997 White House Correspondents' dinner.", '25.6']
]
compare_results(result_1, expected_result_1)

result_2 = run_test(input_stewart_wiki, 5)
expected_result_2 = [
    ['In 1996, Stewart hosted', '1.4'], 
    ['a short-lived talk show', '2.5'], 
    ["entitled, Where's Elvis This Week?", '3.8'], 
    ['which was a half-hour,', '5.5'], 
    ['weekly comedy television program.', '6.8'], 
    ['It aired on Sunday nights in the United', '8.2'], 
    ['Kingdom on BBC Two.', '10.9'], 
    ['It was filmed at the CBS Broadcast Center in New York', '12.2'], 
    ['City and featured a set of panelists,', '15.8'], 
    ['two from the UK and two from the United States,', '18.2'], 
    ['who discussed news items and cultural issues.', '21.4'], 
    ['The show premiered in the UK on October 6, 1996; five episodes aired in total.', '23.9'], 
    ['Notable panelists included Dave Chappelle, Eddie Izzard, Phill Jupitus, Nora Ephron, Craig Kilborn, Christopher Hitchens, Armando Iannucci, Norm Macdonald,', '28.7'], 
    ['and Helen Gurley Brown.', '35.3'], 
    ["In 1997, Stewart was chosen as the host and interviewer for George Carlin's tenth HBO special, George Carlin: 40 Years of Comedy.", '36.6'], 
    ['Stewart had a recurring role in The Larry Sanders Show, playing himself as an occasional substitute and possible successor to late-night talk show host Larry Sanders (played by Garry Shandling).', '43.9'], 
    [" Stewart also headlined the 1997 White House Correspondents' dinner.", '45.3']
]
compare_results(result_2, expected_result_2)


result_3 = run_test(input_problematic, 9)
expected_result_3 = [
    ['First sentence is short.', '1.1'], 
    ['Second sentence is very long,', '2.2'], 
    ['and totally a run on,', '3.9'], 
    ['and would definitely cause problems if this is what the output of the llm was and we only had a quick', '5.5'], 
    ['yield value of one this needs to be broken up thanks.', '12.6'], 
    ['Third sentence also very long that lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '16.2'], 
    ['Fourth sentence also very long fourth sentence that Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '25.9'], 
    ['Fifth sentence also long Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.', '25.9']
]
compare_results(result_3, expected_result_3)

result_4 = run_test(input_problematic, 5)
expected_result_4 = [
    ['First sentence is short.', '1.4'], 
    ['Second sentence is very', '2.4'], 
    ['long, and totally a run', '3.8'], 
    ['on, and would definitely cause problems', '5.4'], 
    ['if this is what the output of the', '7.6'], 
    ['llm was and we only had a quick yield', '10.0'], 
    ['value of one this needs to be broken up thanks.', '13.3'], 
    ['Third sentence also very long that lorem ipsum dolor sit amet, consectetur adipiscing elit,', '16.5'], 
    ['sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam,', '21.1'], 
    ['quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '26.5'], 
    ['Fourth sentence also very long fourth sentence that Lorem ipsum dolor sit amet, consectetur adipiscing elit,', '30.6'], 
    ['sed do eiusmod tempor incididunt ut labore et dolore magna aliqua ut enim ad minim veniam,', '35.8'], 
    ['quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.', '41.2'], 
    ['Fifth sentence also long Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur excepteur sint occaecat cupidatat non proident,', '45.2'], 
    ['sunt in culpa qui officia deserunt mollit anim id est laborum.', '45.8']
]
compare_results(result_4, expected_result_4)
