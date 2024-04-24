from dataclasses import dataclass
from typing import Any, List, Dict
from datetime import datetime

from ..utils.generic import Output


@dataclass
class PredictionOutput(Output):
    value: Any = None
    label: str = None
    score: float = None


@dataclass
class ClassifierOutput(Output):
    input_data: Any = None
    predictions: List[PredictionOutput] = None
    date: datetime = None


class Classifier:
    def __init__(self, *args, return_input=False, **kwargs) -> None:
        """Initiate the classifier (e.g., load the models)"""
        self.return_input = return_input

    def predict(self, input_data: Any, **kwargs) -> Dict[str, ClassifierOutput]:
        """Perform the prediction task on the input

        :raises NotImplementedError: An exception when the class does not implement this function
        :return: A dictionary of classifications with keys representing the nature of the classification.
        :rtype: Dict[str, ClassifierOutput]
        """
        raise NotImplementedError(f"Function `predict` not implemented in {self.__class__.__name__}.")

    def batch_predict(self, input_data: List[Any], **kwargs) -> Dict[str, List[ClassifierOutput]]:
        """Perform the prediction task on the whole batch

        :raises NotImplementedError: An exception when the class does not implement this function
        :return: A dictionary of classifications with keys representing the nature of the classification.
        :rtype: Dict[str, List[ClassifierOutput]]
        """
        raise NotImplementedError(f"Function `batch_predict` not implemented in {self.__class__.__name__}.")
