"""Classify customer messages with the deployed ONNX model."""

import argparse
import json
from pathlib import Path

import torch
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

from customer_service.config import ARTIFACT_DIR


class IntentClassifier:
    def __init__(self, artifact_dir: Path = ARTIFACT_DIR) -> None:
        artifact_dir = Path(artifact_dir)
        manifest = json.loads(
            (artifact_dir / "deployment.json").read_text(encoding="utf-8")
        )
        model_path = artifact_dir / manifest["model_path"]
        labels = json.loads(
            (artifact_dir / manifest["labels_path"]).read_text(encoding="utf-8")
        )

        self.max_length = int(manifest["max_length"])
        self.id2label = labels["id2label"]
        self.tokenizer = AutoTokenizer.from_pretrained(
            artifact_dir / manifest["tokenizer_path"], use_fast=True
        )
        self.model = ORTModelForSequenceClassification.from_pretrained(
            model_path.parent, file_name=model_path.name
        )

    def predict(self, message: str) -> str:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("Message must be a non-empty string.")
        inputs = self.tokenizer(
            message.strip(),
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )
        with torch.inference_mode():
            label_id = self.model(**inputs).logits.argmax(dim=-1).item()
        return self.id2label[str(label_id)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify a customer-service message.")
    parser.add_argument("message", nargs="?", help="Customer message")
    args = parser.parse_args()

    classifier = IntentClassifier()
    message = args.message or input("Customer message: ")
    print(classifier.predict(message))


if __name__ == "__main__":
    main()