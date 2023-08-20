@echo off

:: OpenAI API Key  https://platform.openai.com/
:: - enter your api key into the next line

set OPENAI_API_KEY=Your_API_Key

cd /d %~dp0
TITLE stream2sentence test "stream sentences from llm output"
python test_stream_from_llm.py
pause