import setuptools
import re

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

with open("flat/__init__.py") as f:
    m = re.search(r"__version__ \= \\\"(\d+\.\d+\.\d+)\\\"", f.read())
    version = m.group(1)

setuptools.setup(
    name="flat",
    author="nguuuquaaa",
    url="https://github.com/nguuuquaaa/flat",
    version=version,
    packages=["flat"],
    license="MIT",
    description="Facebook chat (Messenger) wrapper written in python.",
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        "pillow": [
            "pillow"
        ]
    },
    python_requires=">=3.5.3"
)