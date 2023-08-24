import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="stream2sentence", 
    version="0.1.1",
    author="Kolja Beigel",
    author_email="kolja.beigel@web.de",
    description="Real-time processing and delivery of sentences from a continuous stream of characters or text chunks.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/KoljaB/stream2sentence",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=[
        'nltk>=3.6'
    ],
    keywords='realtime, text streaming, stream, sentence, sentence detection, sentence generation, tts, speech synthesis, nltk, text analysis, audio processing, boundary detection, sentence boundary detection'
)