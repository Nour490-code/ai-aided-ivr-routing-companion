"""Intent-classifier settings."""

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = Path(os.getenv("DATA_PATH", PROJECT_ROOT / "data")).expanduser().resolve()
MODELS_DIR = DATA_DIR / "models"
ARTIFACT_DIR = MODELS_DIR / "intent_classifier_onnx"

NEW_BATCH_PATH = DATA_DIR / "new_batch.parquet"
PROCESSED_BATCH_PATH = DATA_DIR / "last_trained_batch.parquet"
TEXT_COLUMN = "instruction"
LABEL_COLUMN = "intent"
VALIDATION_SIZE = 0.2

WINNER_NAME = "electra-small"
WINNER_CHECKPOINT = MODELS_DIR / "transformer_candidates" / WINNER_NAME / "best"
MAX_LENGTH = 24
TRAIN_BATCH_SIZE = 32
EVAL_BATCH_SIZE = 128
MAX_EPOCHS = 5
LEARNING_RATE = 5e-5
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1
SEED = 42
ONNX_OPTIMIZATION_LEVEL = "O2"
