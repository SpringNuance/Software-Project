from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from fastapi.responses import Response, StreamingResponse, JSONResponse
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright
from functools import lru_cache
from collections import OrderedDict

from web_classifier.scrapers import PlaywrightScraper
from web_classifier.extractors.html_extractor import HTMLExtractor
from web_classifier.classifications import text, phishing
from web_classifier.utils.generic import json_dumps
from web_classifier.utils.urls import is_url_image
from web_classifier.utils.images import image_bytes_to_array, resize, image_array_to_bytes, gaussian_blur
from web_classifier.config import Settings


@lru_cache()
def get_settings():
    return Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Load resources
    app.state.extractor = HTMLExtractor()

    app.state.models = {}
    app.state.models["text_classifier"] = text.TextClassifier()
    app.state.models["phishing_classifier"] = phishing.PhishingClassifier(
        text_model_name=settings.phishing_text_path,
        code_model_name=settings.phishing_code_path,
        img_model_name=settings.phishing_image_path,
        url_model_name=settings.phishing_url_path,
        url_prediction_threshold=settings.phishing_url_threshold,
        models_path=settings.phishing_model_path,
    )

    s = PlaywrightScraper(headless=settings.headless, timeout=0)
    async with async_playwright() as playwright:
        await s.setup(playwright)
        app.state.scraper = s

        yield

        # clear async resources

    # clear other resources


app = FastAPI(lifespan=lifespan)


templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


class URLPayload(BaseModel):
    url: str


def classify_content(content: str) -> str:
    return app.state.classifiers


@app.get("/")
async def homepage(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/classify/url/")
async def classify_url(payload: URLPayload):
    url = payload.url
    try:
        scraped_output = await app.state.scraper.scrape(url)
        classifications = {}
        processed_html = None

        # Classify the html/text
        if scraped_output.body and scraped_output.body[-7:].strip().endswith(b"</html>"):
            processed_html = app.state.extractor.extract(html=scraped_output.body, url=scraped_output.url)

            title = " ".join(processed_html.titles)
            if title:
                classifications["title"] = app.state.models["text_classifier"].predict(title)

            content = " ".join(processed_html.text["content"])
            if content:
                classifications["content"] = app.state.models["text_classifier"].predict(content)

            classifications["phishing"] = app.state.models["phishing_classifier"].predict(
                scraped_output, processed_html
            )

        # Classify screenshot
        screenshot = scraped_output.screenshot
        # classification code goes here ...

        # Final verdict
        verdict = classifications["phishing"]["content"].predictions[0].label

        # Prepare output
        screenshot = image_bytes_to_array(screenshot)
        screenshot = resize(screenshot, 768)
        screenshot = screenshot if verdict != "adult" else gaussian_blur(screenshot)
        screenshot = image_array_to_bytes(screenshot)
        scraped_output.screenshot = screenshot

        scraped_output["body"] = None
        scraped_output["full_screenshot"] = None

        # remove request body
        for _r in scraped_output.requests:
            _r["response"] = None

        # remove classification input

        result = {}
        result["url"] = scraped_output.url
        result["screenshot"] = screenshot
        result["classifications"] = classifications
        result["verdict"] = verdict

        json_result = json_dumps(result)

        return Response(content=json_result, media_type="application/json")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
