from setuptools import find_packages, setup

with open("README.md") as f:
    README = f.read()

setup(
    name='pychannels',
    url="https://github.com/wyfo/pychannels",
    author="Joseph Perez",
    author_email="joperez@hotmail.fr",
    description="Asyncion channels for python",
    long_description=README,
    long_description_content_type="text/markdown",
    version='0.1.0',
    packages=find_packages(include=["channels"]),
    install_requires=[],
    python_requires=">=3.6",
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
)
