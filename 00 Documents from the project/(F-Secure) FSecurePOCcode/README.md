# Project overview

|                         |                                                                                  |
|-------------------------|----------------------------------------------------------------------------------|
| **Compass page**:       | [General Overview of the Project](https://withsecure.atlassian.net/wiki/spaces/FSLABS/pages/354681927/)              |
| **Documentation**: | [Docstrings, Development and Deployment Details](http://docs.ds.fsapi.com/)   |
| **Bitbucket**:          | [Source Code](https://stash.f-secure.com/projects/TPE/repos/web-classifier/browse)                           |
| **Jira**:               | [Project Epic](https://withsecure.atlassian.net/browse/TPE-1780)                                     |
| **Jenkins**:            | [Jenkins Job](https://helcssmaster01.fi.f-secure.com/blue/organizations/jenkins) |
| **PRD Azkaban**:        | [Not available yet](https://bigdata.rds.f-secure.com/)                             |
| **STG Azkaban**:        | [Not available yet](https://bigdata.rds-stg.fsxt.net/)                             |
| **CI Azkaban**:         | [Not available yet](https://bigdata.rds-ci.fsxt.net/)                             |


## Description
This project aims to facilitate classifying websites such as detecting adult, phishing and malicious web pages. There are three main components of this project, which are:

- **Web scraping**: fetch the content of URLs using either curl or playwright (async).
- **Data and feature extraction**: process the scraped data to extract meaningful features for analysis and classification.
- **Classification**: a CLI and a simple UI for running classification models or the full inference pipelines.

Installation and usage of each of the components are described in the below sections:

### Scraper
The goal of the scraper is to fetch the content behind a given URL. There are two types of scrapers implemented, which are:
- [**cURL**](https://github.com/pycurl/pycurl): curl (*client URL*) is a command line tool for communicating with servers. Pycurl is a python interface for libcurl and supports many protocols.
- [**playwright**](https://github.com/microsoft/playwright-python): [playwright](https://playwright.dev/) is developed by Microsoft and it's a tool for automatically testing web apps and sites. In practice, playwright communicates with a browser (e.g., chrome and firefox). playwright allows asynchronous calls/connections, resulting in faster interactions with the browser. 

**[NOTES]** 
- cURL queries the given URL only, whereas playwright renders the URL in a browser.
- Some websites can detect cURL requests, try forging the headers. If forging didn't work, use playwright. 
- Also, some websites are capable of detecting headless rendering, use headful rendering to bypass this restrection.
- For bulk analysis without caring about failures (e.g., for data collection), cURL is better due to its rapid speed.
- Binary data is automatically encoded in base64.
- It's important to pick a good balance between number of workers/threads and timeout limit depending on the network and hardware resources.
- Scraping is different than crawling as crawling generally navigates and follows links to iteratively collect more data. Crawling is outside of the scope of the project for now.

#### Installation
To use the scraper CLI, use Python **+3.11** as it has support for `ExceptionGroup` that allows grouping thrown exceptions from asynchronous functions.

To install the script, run the below commands:

```
pip install '.[scrape]'
python -m playwright install
```

#### Usage

##### CLI

Both cURL and playwright can be used to scrape a list of URLs using the CLI. The input to the CLI is a text file with one URL per line, and the output is file containing the results (in JSON format) per line. The output is not necessary in the same order of the input as requests are sent in parallel. The CLI script is [cli/scraper.py](web_classifier/cli/scraper.py). 

An example for running the scraper:

`PYTHONPATH=. python web_classifier/cli/scraper.py --scraper curl -i ./web_classifier/tests/fixtures/test_urls.txt -o /tmp/scraper_output.jsonl`

To adjust the number of workers/threads, use `--num_conn` for `curl` and `--num_pages` for `playwright`. For additional details on the parameters to pass for each scraper, see [CurlScraper](web_classifier/scrapers/curl_scraper.py) and [PlaywrightScraper](web_classifier/scrapers/playwright_scraper.py).

##### Code or Notebooks
Please refer to [cli/scraper.py](web_classifier/cli/scraper.py) for an example usage. More advanced use cases will be added later.

### Feature Extraction
The purpose of the feature extraction is to process the scraper output and extract all the relevant and useful pieces of information from it. Examples of features/data that could be extracted:

- HTML features
    - titles ✓
    - meta information ✓
    - iframes ✓
    - forms ✓
    - statistics ✓
    - ...
- Image features
    - dominant colors ✓
    - logo selection
- Text features
    - brand names
- hashes
    - sha1 and 2
- ... many more

#### Installation

```
pip install '.[extract]'
```

#### Usage

##### CLI
`PYTHONPATH=. python web_classifier/cli/extractor.py  -i /tmp/scraper_output.jsonl -o /tmp/extracter_output.jsonl`

### Classification

The classifier is currently a web service that, scrapes a given URL, extracts the important features and then classifies the website based on the content. 

#### Installation
```
pip install .[full]
```
Set up the local environment by copying the `.env.example` to `.env` and modifying it's content to point to the locations of the models.

#### Usage

```
cd web_classifier
PYTHONPATH=.. uvicorn app:app
```