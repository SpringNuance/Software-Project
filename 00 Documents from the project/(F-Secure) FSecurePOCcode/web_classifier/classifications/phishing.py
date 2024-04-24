from typing import Dict, Union, List, Any
from datetime import datetime
import numpy as np
from xgboost import XGBClassifier
import io
import pickle
from collections import Counter
import pandas as pd
from PIL import Image

import dhash

dhash.force_pil()  # Use PIL

from transformers import (
    AutoTokenizer,
    AutoModel,
    AutoImageProcessor,
    AutoModelForImageClassification,
    DistilBertForSequenceClassification,
)

from ..scrapers.base import ScraperOutput
from ..extractors.html_extractor import HTMLExtractorOutput
from ..utils.urls import get_domain
from ..utils.images import base64_to_image
from ..utils.files import get_lines, sha1sum

from .classifier import Classifier, ClassifierOutput, PredictionOutput


class PhishingClassifier(Classifier):
    def __init__(
        self,
        *args,
        text_model_name,
        code_model_name,
        img_model_name,
        url_model_name,
        models_path,
        tokenizer_max_length=512,
        url_prediction_threshold=0.6,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        # @TODO: Models could be quantized and optimized for inference.

        self.text_tokenizer = AutoTokenizer.from_pretrained(text_model_name)
        # Omitted as they're not loaded for the demo
        # self.text_model = AutoModel.from_pretrained(text_model_name)
        # self.text_model.eval()

        # Trained on GO, Java, Javascript, PHP, Python and Ruby
        # @TODO: Training a model for web and web attacks that includes (e.g., shell, HTML, CSS would produce better embeddings)
        self.code_tokenizer = AutoTokenizer.from_pretrained(code_model_name)
        # Omitted as they're not loaded for the demo
        # self.code_model = AutoModel.from_pretrained(code_model_name)
        # self.code_model.eval()

        self.img_preprocessor = AutoImageProcessor.from_pretrained(img_model_name)
        # Omitted as they're not loaded for the demo
        # self.img_model = AutoModelForImageClassification.from_pretrained(img_model_name)
        # self.img_model.eval()

        self.url_tokenizer = AutoTokenizer.from_pretrained(url_model_name)
        self.url_model = DistilBertForSequenceClassification.from_pretrained(
            url_model_name
        )
        self.url_model.eval()

        self.tokenizer_max_length = tokenizer_max_length
        self.url_prediction_threshold = url_prediction_threshold

        self.phishingkit_data = pd.read_csv(
            f"{models_path}/phishing_kit_page_dhashes.csv"
        )
        self.phishingkit_dhash = self.phishingkit_data.screenshot_dhash.map(
            lambda _x: int(_x, 16)
        )

        self.phishing_kits_sha1 = {
            _s.strip() for _s in get_lines(f"{models_path}/sha1.txt")
        }

        with io.open(f"{models_path}/html_vectorizer.pkl", "rb") as inp_f:
            self.html_vectorizer = pickle.load(inp_f)

        with io.open(f"{models_path}/text_vectorizer.pkl", "rb") as inp_f:
            self.text_vectorizer = pickle.load(inp_f)

        self.atomic_models = []
        for _i in range(5):
            _atomic_model = XGBClassifier()
            _atomic_model.load_model(f"{models_path}/atomic_{_i}.json")

            self.atomic_models.append(_atomic_model)

        self.final_model = XGBClassifier()
        self.final_model.load_model(f"{models_path}/phishnet.json")

        self._resource_types = [
            "document",
            "stylesheet",
            "image",
            "media",
            "font",
            "script",
            "texttrack",
            "xhr",
            "fetch",
            "eventsource",
            "websocket",
            "manifest",
            "other",
        ]

        self.classes = {0: "benign", 1: "phishing"}

    def resources_type_vector(self, requests):
        _counter = Counter([request["resource_type"] for request in requests])
        return np.array(
            [_counter[_rt] if _rt in _counter else 0 for _rt in self._resource_types]
        )

    def softmax(self, _outputs):
        maxes = np.max(_outputs, axis=-1, keepdims=True)
        shifted_exp = np.exp(_outputs - maxes)
        return shifted_exp / shifted_exp.sum(axis=-1, keepdims=True)

    def url_classification(self, urls):
        outputs = self.url_model(
            **self.url_tokenizer(
                urls,
                padding="max_length",
                truncation=True,
                max_length=self.tokenizer_max_length,
                return_tensors="pt",
            )
        )
        logits = outputs.logits.detach().numpy()
        scores = self.softmax(logits)
        y = 1.0 * (scores[:, 1] >= self.url_prediction_threshold)
        return y, scores[:, 1]

    def predict(
        self, scraped_output: ScraperOutput, extracted_html: HTMLExtractorOutput
    ):
        titles_str = " ".join(extracted_html.titles)
        full_text_str = " ".join(extracted_html.text["full_text"])
        full_content = titles_str + " " + full_text_str

        domain = get_domain(extracted_html.url)

        urls_domain = [get_domain(_u) for _u in extracted_html.urls]

        external_urls = [
            _u for _u, _d in zip(extracted_html.urls, urls_domain) if _d != domain
        ]

        external_domains = {_d for _d in urls_domain if _d != domain}

        stats = extracted_html.stats.copy()
        stats["external_domains"] = len(external_domains)
        stats["external_urls"] = len(external_urls)
        stats["internal_domains"] = len(extracted_html.urls) - stats["external_urls"]

        stats["js_count"] = stats["script"] + len(
            [
                request["resource_type"]
                for request in scraped_output.requests
                if request["resource_type"] == "script"
            ]
        )
        stats["css_count"] = stats["style"] + len(
            [
                request["resource_type"]
                for request in scraped_output.requests
                if request["resource_type"] == "stylesheet"
            ]
        )

        title_tokens = self.text_tokenization(titles_str, max_length=100)
        text_tokens = self.text_tokenization(full_text_str)

        brand_name = domain.replace("([\d\.]+)?\.(.*)$", "")
        domain_tokens = self.text_tokenization(domain, max_length=100)
        brand_tokens = self.text_tokenization(brand_name, max_length=100)
        external_domains_tokens = self.text_tokenization(" ".join(external_domains))

        _resources_type_vector = self.resources_type_vector(scraped_output.requests)

        text_vectors = self.text_vectorizer.transform([full_content]).toarray()

        html_vectors = self.html_vectorizer.transform([scraped_output.body]).toarray()

        stats_features = [
            "meta",
            "script",
            "link",
            "style",
            "iframe",
            "div",
            "span",
            "svg",
            "a",
            "li",
            "img",
            "p",
            "form",
            "input",
            "button",
            "table",
            "code",
            "textarea",
            "video",
            "js_count",
            "css_count",
            "internal_domains",
            "external_urls",
            "external_domains",
        ]

        features_per_model = [
            [
                np.concatenate(
                    [[stats[_f] for _f in stats_features], _resources_type_vector],
                    axis=0,
                )
            ],
            [np.concatenate([title_tokens, text_tokens], axis=0)],
            text_vectors,
            html_vectors,
            [
                np.concatenate(
                    [brand_tokens, domain_tokens, external_domains_tokens], axis=0
                )
            ],
        ]

        # predict per model
        _atomic_preds = [
            self.atomic_models[_i].predict_proba(_f)[0][1]
            for _i, _f in enumerate(features_per_model)
        ]

        url_pred, url_scores = self.url_classification([scraped_output.url])
        url_pred, url_scores = int(url_pred[0]), url_scores[0]

        screenshot = (
            base64_to_image(scraped_output.screenshot)
            if isinstance(scraped_output.screenshot, str)
            else Image.open(io.BytesIO(scraped_output.screenshot))
        )
        screenshot_pred = self.get_lookalike_phishingkit(screenshot)

        screenshot_pred = screenshot_pred[1]

        requests_sha1 = set()
        for _r in scraped_output.requests:
            if _r.response and _r.response.body:
                try:
                    requests_sha1 |= {
                        sha1sum(str(_r.response.body, "utf-8").encode("utf-8")),
                    }
                except:
                    pass

        num_shared_sha1 = len(requests_sha1 & self.phishing_kits_sha1)

        # predict final
        pred = self.final_model.predict_proba(
            [
                _atomic_preds + [screenshot_pred, num_shared_sha1],
            ]
        )[:, 1]

        content_pred, content_score = int(pred[0] >= 0.5), pred[0]

        return {
            "url": ClassifierOutput(
                input_data=None if self.return_input else None,
                predictions=[
                    PredictionOutput(
                        value=url_pred,
                        label=self.classes[url_pred],
                        score=url_scores if url_pred else 1 - url_scores,
                    ),
                ],
                date=datetime.now(),
            ),
            "content": ClassifierOutput(
                input_data=None if self.return_input else None,
                predictions=[
                    PredictionOutput(
                        value=content_pred,
                        label=self.classes[content_pred],
                        score=content_score if content_pred else 1 - content_score,
                    ),
                ],
                date=datetime.now(),
            ),
        }

    def text_tokenization(self, text, max_length=512):
        return self.text_tokenizer(
            text, padding="max_length", truncation=True, max_length=max_length
        ).input_ids

    def code_tokenization(self, code, max_length=512):
        return self.code_tokenizer(
            code, padding="max_length", truncation=True, max_length=max_length
        ).input_ids

    def text_embeddings(self, text):
        outputs = self.text_model(
            **self.text_tokenizer(
                text,
                padding="max_length",
                truncation=True,
                max_length=self.tokenizer_max_length,
                return_tensors="pt",
            )
        )
        hidden_states = outputs.last_hidden_state
        first_token_tensor = hidden_states[
            :, 0
        ]  # first token of the whole last layer ([CLS])
        return first_token_tensor.detach().numpy()

    def code_embeddings(self, text):
        outputs = self.code_model(
            **self.code_tokenizer(
                text,
                padding="max_length",
                truncation=True,
                max_length=self.tokenizer_max_length,
                return_tensors="pt",
            )
        )
        hidden_states = outputs.last_hidden_state
        first_token_tensor = hidden_states[
            :, 0
        ]  # first token of the whole last layer ([CLS])
        return first_token_tensor.detach().numpy()

    def img_embeddings(self, image):
        rgb_im = image.convert("RGB")
        img_processed = self.img_preprocessor(images=rgb_im, return_tensors="pt")
        outputs = self.img_model.mobilenet_v2(
            **img_processed, output_hidden_states=True, return_dict=True
        )
        return outputs.pooler_output.detach().numpy()

    def get_img_dhash(self, image):
        return dhash.dhash_int(image, size=16)  # Size=16 is slower and more accurate

    def get_lookalike_phishingkit(self, image):
        image_dhash = self.get_img_dhash(image)
        # Convert Hex to int
        # Then get the distance
        dist = self.phishingkit_dhash.map(
            lambda _phk_dhash: dhash.get_num_bits_different(_phk_dhash, image_dhash)
        )
        most_sim_idx = np.argmin(dist, axis=0)
        most_sim_kit_author = self.phishingkit_data.url[most_sim_idx]
        most_sim_dist = dist[most_sim_idx]
        return most_sim_kit_author, most_sim_dist
