from typing import Dict
from datetime import datetime
from ftlangdetect.detect import get_or_load_model

from .classifier import Classifier, ClassifierOutput, PredictionOutput


class TextClassifier(Classifier):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Download the models if aren't present
        self.lang_detect_model = get_or_load_model(low_memory=True)

    def predict(self, input_data: str, **kwargs) -> Dict[str, ClassifierOutput]:
        # Language Detection
        labels, scores = self.lang_detect_model.predict(input_data.replace("\n", ""))
        label = labels[0].replace("__label__", "")
        lang_prediction = PredictionOutput(value=label, label=label, score=min(float(scores[0]), 1.0))

        lang_pred = ClassifierOutput(
            input_data=input_data if self.return_input else None,
            predictions=[
                lang_prediction,
            ],
            date=datetime.now(),
        )

        return {"language": lang_pred}
