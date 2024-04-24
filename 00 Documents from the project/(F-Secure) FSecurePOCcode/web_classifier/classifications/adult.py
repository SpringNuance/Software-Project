from typing import Dict, Union, List, Any
from datetime import datetime
import numpy as np
import onnxruntime as ort

from .classifier import Classifier, ClassifierOutput, PredictionOutput
from ..utils.images import resize, center_crop, normalize, image_bytes_to_array


class AdultClassifier(Classifier):
    def __init__(self, *args, image_model_path=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.image_model = ort.InferenceSession(image_model_path)
        self.image_categories = ["drawings", "hentai", "neutral", "porn", "sexy"]

        self.resize_dim = 256
        self.image_dim = 224

    def _transform_image(self, image):
        x = resize(image, self.resize_dim, self.resize_dim)
        x = center_crop(x, self.image_dim, self.image_dim)
        x = x / 255
        return x

    def predict(self, input_data: List[Any], **kwargs) -> Dict[str, ClassifierOutput]:
        result = self.batch_predict(
            [
                input_data,
            ]
        )
        return result

    def batch_predict(self, input_data: Dict[str, List[Any]], **kwargs) -> Dict[str, List[ClassifierOutput]]:
        images = input_data.get("images", [])
        return {"images": self.batch_predict_images(images)}

    def batch_predict_images(self, input_data: List[bytes], **kwargs) -> List[ClassifierOutput]:
        # convert to numpy arrays then to an image array
        img_arrays = [image_bytes_to_array(image_bytes) for image_bytes in input_data]

        # transform images for the model
        x = [self._transform_image(_x) for _x in img_arrays]

        x = np.array(x)

        x = x.astype(np.float32)

        model_predictions = self.image_model.run(None, {"input_1": x})
        model_predictions = model_predictions[0]
        predictions = np.argsort(model_predictions, axis=1)
        predictions = np.flip(predictions, axis=1)
        scores = np.take_along_axis(model_predictions, predictions, axis=1)

        image_classifications = []
        for _i, _p in enumerate(predictions):
            image_prediction = []
            for _value, _score in zip(_p, scores[_i]):
                image_prediction.append(
                    PredictionOutput(value=_value, label=self.image_categories[_value], score=_score)
                )

            image_classification = ClassifierOutput(
                input_data=input_data if self.return_input else None,
                predictions=image_prediction,
                date=datetime.now(),
            )

            image_classifications.append(image_classification)
        return image_classifications
