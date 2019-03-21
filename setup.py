import setuptools

with open("README.md") as f:
    readme = f.read()

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setuptools.setup(
    name="flat",
    author="nguuuquaaa",
    url="https://github.com/nguuuquaaa/flat",
    version="0.0.1",
    packages=["flat"],
    license="MIT",
    description="Facebook chat (Messenger) wrapper written in python."
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        "pillow": [
            "pillow"
        ]
    },
    python_requires=">=3.5.3"
)