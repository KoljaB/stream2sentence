import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="stream2sentence", 
    version="1.0.0",
    author="Kolja Beigel",
    author_email="kolja.beigel@web.de",
    description="Real-time processing and delivery of sentences from a continuous stream of characters or text chunks.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/KoljaB/stream2sentence",
    packages=setuptools.find_packages(),
    package_data={"stream2sentence": ["data/*.json"]},
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.10',
    install_requires=[
        'nltk==3.9.4',
        'emoji==2.15.0',
        'stanza==1.13.0'
    ],
    keywords='realtime, text streaming, stream, sentence, sentence detection, sentence generation, tts, speech synthesis, nltk, text analysis, audio processing, boundary detection, sentence boundary detection'
)
