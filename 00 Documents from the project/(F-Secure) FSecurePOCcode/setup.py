"""Setup.py for project."""
import subprocess

from setuptools import find_packages, setup

# distutils need to be imported after setuptools to avoid possible problems and suppress warnings
from distutils.cmd import Command  # noqa


class UpdatePipConf(Command):
    description = "Write index-url and extras-index-url to pip.conf for venv (if venv is not active, this will fail)"
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        index_url = "https://artifactory.f-secure.com/artifactory/api/pypi/pypi/simple"
        subprocess.check_output(["pip", "config", "--site", "set", "global.index-url", index_url])


classifiers = [
    # How mature is this project? Common values are
    #   2 - Pre-Alpha
    #   3 - Alpha
    #   4 - Beta
    #   5 - Production/Stable
    "Development Status :: 2 - Pre-Alpha",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: Implementation :: CPython",
    "License :: Other/Proprietary License",
    "Private :: Do Not Upload",
]

# PROJECT RUNTIME REQUIREMENTS: install_require, emr_require, tests_require and dev_require

# These are installed with pip, if you need some non-pip packages add the commands that install them directly
# to the bootstrap script.

# Minimum runtime requirements, this should contain what is required e.g. for model inference.
install_require = [
    "orjson",
    "aiofiles",
    "tldextract",
    "tqdm",
    "fastapi",
    "jinja2",
    "uvicorn[standard]",
]

# If project is run as an Azkaban flow, these requirements will be installed to all EMR nodes by the bootstrap script.
# In addition to these, everything specified in install_require will also be installed to cluster nodes.
emr_require = ["boto3"]  # Example EMR dependency (modify or remove as needed)

scrapping_require = [
    "pycurl",
    "certifi",
    "playwright",
]

extraction_require = [
    "requests_html",
    "justext",
    "trafilatura",
]

classification_require = ["onnxruntime", "fasttext-langdetect"]

# Tools for running tests etc. but which are not required for software to run in production.
tests_require = [
    "pyspark>2.4.3",
    "pyarrow",
    "pandas",
    "coverage",
    "pytest",
    "flake8>=3.8.4,<4.0.0",
    "flake8-import-order>=0.18.1,<1.0.0",
    "flake8-print>=3.1.4,<4.0.0",
    "flake8-eradicate>=1.0.0,<2.0.0",
    "pytest-flake8>=1.0.6,<2.0.0",
    "pytest-black ; python_version >= '3.6'",
    "pytest-cov",
    "pytest-runner",
    "pytest-timeout",
    "setuptools>=12",
    "wheel",
    "PyYaml",
]

# Tools and libraries required for developing the software, creating documentation, etc.
dev_require = ["jinja2-cli", "fs-azkaban-tools", "recommonmark", "sphinx", "sphinx-rtd-theme", "sphinx-markdown-tables"]

# Parse version from git tag
git_version = subprocess.check_output("git describe --always".split()).strip().decode("ascii")
# Replace the first '-' with + and the later ones with '.'
git_version = git_version.replace("-", "+", 1).replace("-", ".")

with open("README.md", encoding="utf-8") as f:
    readme = f.read()

extras = dict()
extras["scrape"] = scrapping_require
extras["extract"] = extraction_require
extras["classify"] = classification_require
extras["full"] = scrapping_require + extraction_require + classification_require
extras["dev"] = emr_require + tests_require + dev_require
extras["emr"] = emr_require

setup(
    name="fs-web-classifier",
    description="A toolbox for scraping, extracting and classifying the web.",
    keywords=["AICE"],
    license="F-Secure",
    url="https://stash.f-secure.com/projects/DI/repos/di-project-template-python/browse",
    long_description=readme,
    version=git_version,
    author="TPE",
    author_email="khalid.alnajjar@f-secure.com",
    zip_safe=False,
    packages=find_packages("."),
    classifiers=classifiers,
    install_requires=install_require,
    extras_require=extras,
    cmdclass={"update_pip_conf": UpdatePipConf},
)
