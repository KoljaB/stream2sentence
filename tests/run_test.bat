@echo off

:: switch to current execution directory
cd /d %~dp0

TITLE basic stream2sentence test 
python test_stream2sentence.py
pause