"""Retrain and export the intent classifier when new_batch.parquet exists."""

import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
import onnx
import pandas as pd
from onnxruntime.quantization import quantize_dynamic
from optimum.exporters.onnx import main_export
from optimum.onnxruntime.configuration import AutoQuantizationConfig, ORTConfig
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from transformers import (
    AutoConfig,
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

from customer_service.config import (
    ARTIFACT_DIR,
    EVAL_BATCH_SIZE,
    LABEL_COLUMN,
    LEARNING_RATE,
    MAX_EPOCHS,
    MAX_LENGTH,
    MODELS_DIR,
    NEW_BATCH_PATH,
    ONNX_OPTIMIZATION_LEVEL,
    PROCESSED_BATCH_PATH,
    SEED,
    TEXT_COLUMN,
    TRAIN_BATCH_SIZE,
    VALIDATION_SIZE,
    WARMUP_RATIO,
    WEIGHT_DECAY,
    WINNER_CHECKPOINT,
    WINNER_NAME,
)


class IntentDataset(Dataset):
    def __init__(self, frame, tokenizer, label2id):
        self.tokens = tokenizer(
            frame[TEXT_COLUMN].tolist(), truncation=True, max_length=MAX_LENGTH
        )
        self.labels = frame[LABEL_COLUMN].map(label2id).tolist()

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, index):
        item = {name: values[index] for name, values in self.tokens.items()}
        item["labels"] = self.labels[index]
        return item


def read_data(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path, columns=[TEXT_COLUMN, LABEL_COLUMN]).dropna()
    frame[TEXT_COLUMN] = frame[TEXT_COLUMN].str.strip()
    frame[LABEL_COLUMN] = frame[LABEL_COLUMN].str.strip()
    frame = frame[(frame[TEXT_COLUMN] != "") & (frame[LABEL_COLUMN] != "")]
    if frame.empty:
        raise ValueError(f"No valid rows found in {path}")
    return frame


def compute_metrics(result):
    predictions = np.argmax(result.predictions, axis=-1)
    return {"macro_f1": f1_score(result.label_ids, predictions, average="macro")}


def export_onnx(checkpoint_dir: Path, tokenizer) -> str:
    fp32_dir = ARTIFACT_DIR / "fp32"
    int8_dir = ARTIFACT_DIR / "int8"
    shutil.rmtree(fp32_dir, ignore_errors=True)
    shutil.rmtree(int8_dir, ignore_errors=True)
    fp32_dir.mkdir(parents=True)
    int8_dir.mkdir(parents=True)

    tokenizer.save_pretrained(ARTIFACT_DIR)
    main_export(
        model_name_or_path=str(checkpoint_dir),
        output=fp32_dir,
        task="text-classification",
        optimize=ONNX_OPTIMIZATION_LEVEL,
        do_validation=True,
    )
    fp32_file = next(fp32_dir.glob("*.onnx"))

    quantization = AutoQuantizationConfig.avx2(
        is_static=False, per_channel=True, reduce_range=False
    )
    int8_file = int8_dir / f"{fp32_file.stem}_quantized.onnx"
    quantize_dynamic(
        model_input=fp32_file,
        model_output=int8_file,
        op_types_to_quantize=quantization.operators_to_quantize,
        per_channel=quantization.per_channel,
        reduce_range=quantization.reduce_range,
        weight_type=quantization.weights_dtype,
        extra_options={"DefaultTensorType": onnx.TensorProto.FLOAT},
    )
    AutoConfig.from_pretrained(fp32_dir).save_pretrained(int8_dir)
    ORTConfig(quantization=quantization).save_pretrained(int8_dir)
    return str(int8_file.relative_to(ARTIFACT_DIR))


def retrain() -> bool:
    if not NEW_BATCH_PATH.exists():
        print(f"No new batch found at {NEW_BATCH_PATH}")
        return False

    labels = json.loads((ARTIFACT_DIR / "labels.json").read_text(encoding="utf-8"))
    new_data = read_data(NEW_BATCH_PATH)
    unknown_labels = set(new_data[LABEL_COLUMN]) - set(labels["label2id"])
    if unknown_labels:
        raise ValueError(f"Unknown intent labels: {sorted(unknown_labels)}")

    new_data = new_data.drop_duplicates()
    label_counts = new_data[LABEL_COLUMN].value_counts()
    if label_counts.min() < 2:
        raise ValueError("Each intent needs at least two rows for a train/validation split")
    validation_rows = max(len(label_counts), round(len(new_data) * VALIDATION_SIZE))
    train_data, validation_data = train_test_split(
        new_data,
        test_size=validation_rows,
        random_state=SEED,
        stratify=new_data[LABEL_COLUMN],
    )
    tokenizer = AutoTokenizer.from_pretrained(WINNER_CHECKPOINT, use_fast=True)

    with tempfile.TemporaryDirectory(dir=MODELS_DIR) as temporary_dir:
        output_dir = Path(temporary_dir)
        trainer = Trainer(
            model=AutoModelForSequenceClassification.from_pretrained(WINNER_CHECKPOINT),
            args=TrainingArguments(
                output_dir=str(output_dir / "training"),
                learning_rate=LEARNING_RATE,
                weight_decay=WEIGHT_DECAY,
                warmup_ratio=WARMUP_RATIO,
                num_train_epochs=MAX_EPOCHS,
                per_device_train_batch_size=TRAIN_BATCH_SIZE,
                per_device_eval_batch_size=EVAL_BATCH_SIZE,
                eval_strategy="epoch",
                save_strategy="epoch",
                save_total_limit=1,
                load_best_model_at_end=True,
                metric_for_best_model="macro_f1",
                greater_is_better=True,
                report_to="none",
                seed=SEED,
            ),
            train_dataset=IntentDataset(train_data, tokenizer, labels["label2id"]),
            eval_dataset=IntentDataset(validation_data, tokenizer, labels["label2id"]),
            processing_class=tokenizer,
            data_collator=DataCollatorWithPadding(tokenizer),
            compute_metrics=compute_metrics,
        )
        trainer.train()
        checkpoint_dir = output_dir / "best_model"
        trainer.save_model(checkpoint_dir)
        validation_macro_f1 = trainer.evaluate()["eval_macro_f1"]
        model_path = export_onnx(checkpoint_dir, tokenizer)

        shutil.copytree(checkpoint_dir, WINNER_CHECKPOINT, dirs_exist_ok=True)

    manifest = {
        "model_name": WINNER_NAME,
        "source_checkpoint": str(WINNER_CHECKPOINT),
        "precision": "int8",
        "model_path": model_path,
        "tokenizer_path": ".",
        "labels_path": "labels.json",
        "max_length": MAX_LENGTH,
        "validation_macro_f1": validation_macro_f1,
    }
    (ARTIFACT_DIR / "deployment.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    NEW_BATCH_PATH.replace(PROCESSED_BATCH_PATH)
    print(f"Published retrained model to {ARTIFACT_DIR}")
    return True


def main() -> None:
    retrain()


if __name__ == "__main__":
    main()
