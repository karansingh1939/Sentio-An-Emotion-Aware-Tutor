"""
train_emotion_model.py -- FER2013 Training Pipeline
====================================================
End-to-end script for training the CNN emotion classifier.

Steps
-----
1. Load & preprocess FER2013 dataset (CSV or image folder format)
2. Apply data augmentation (rotation, flip, zoom, shift)
3. Build model via EmotionModelBuilder (custom_cnn / mobilenet / resnet)
4. Train with callbacks: EarlyStopping, ReduceLR, ModelCheckpoint, TensorBoard
5. Evaluate on test split -- print classification report + confusion matrix
6. Export final model to models/emotion_model.h5

Dataset
-------
Download FER2013 from Kaggle:
  https://www.kaggle.com/datasets/msambare/fer2013
Place fer2013.csv (or the train/test image folders) inside data/

Run
---
    python train_emotion_model.py
    python train_emotion_model.py --backbone mobilenet --epochs 30
    python train_emotion_model.py --data_dir data/train --test_dir data/test
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np

from sentio.ai.emotion_detector import EmotionDetector
from sentio.config import LOG_DIR, dataset_cfg, emotion_cfg

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# DATA LOADERS
# ─────────────────────────────────────────────


def load_fer2013_csv(csv_path):
    """
    Load FER2013 from the official CSV format.

    CSV columns: emotion (int 0-6), pixels (space-separated), Usage (Training/PublicTest/PrivateTest)

    Returns:
        (X_train, y_train, X_val, y_val, X_test, y_test)
        All X arrays: float32 (N, 48, 48, 1) normalised 0-1
        All y arrays: int32  (N,)
    """
    import pandas as pd

    logger.info("Loading FER2013 CSV: %s", csv_path)
    df = pd.read_csv(csv_path)

    def _parse_split(usage_label):
        subset = df[df["Usage"] == usage_label]
        pixels = subset["pixels"].tolist()
        X = (
            np.array(
                [np.fromstring(p, dtype=np.uint8, sep=" ").reshape(48, 48, 1) for p in pixels],
                dtype=np.float32,
            )
            / 255.0
        )
        y = subset["emotion"].values.astype(np.int32)
        return X, y

    X_train, y_train = _parse_split("Training")
    X_val, y_val = _parse_split("PublicTest")
    X_test, y_test = _parse_split("PrivateTest")

    logger.info(
        "Dataset loaded | train=%d  val=%d  test=%d",
        len(X_train),
        len(X_val),
        len(X_test),
    )
    return X_train, y_train, X_val, y_val, X_test, y_test


def load_image_folders(train_dir, test_dir, val_split=0.2):
    """
    Load dataset from image folders arranged as:
        train/angry/*.jpg  train/happy/*.jpg ...
        test/angry/*.jpg   test/happy/*.jpg  ...

    Returns:
        (X_train, y_train, X_val, y_val, X_test, y_test)
    """
    import cv2
    from sklearn.model_selection import train_test_split

    classes = emotion_cfg.CLASSES

    def _load_dir(folder):
        folder = Path(folder)
        X, y = [], []
        for label_idx, cls in enumerate(classes):
            cls_dir = folder / cls
            if not cls_dir.exists():
                logger.warning("Class folder not found: %s", cls_dir)
                continue
            for img_path in cls_dir.glob("*"):
                if img_path.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp"):
                    continue
                img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)
                if img is None:
                    continue
                img = cv2.resize(img, (emotion_cfg.IMG_SIZE, emotion_cfg.IMG_SIZE))
                X.append(img.reshape(emotion_cfg.IMG_SIZE, emotion_cfg.IMG_SIZE, 1))
                y.append(label_idx)
        X = np.array(X, dtype=np.float32) / 255.0
        y = np.array(y, dtype=np.int32)
        return X, y

    logger.info("Loading image folders: %s / %s", train_dir, test_dir)
    X_all, y_all = _load_dir(train_dir)
    X_test, y_test = _load_dir(test_dir)

    X_train, X_val, y_train, y_val = train_test_split(
        X_all,
        y_all,
        test_size=val_split,
        random_state=dataset_cfg.RANDOM_SEED,
        stratify=y_all,
    )

    logger.info(
        "Dataset loaded | train=%d  val=%d  test=%d",
        len(X_train),
        len(X_val),
        len(X_test),
    )
    return X_train, y_train, X_val, y_val, X_test, y_test


# ─────────────────────────────────────────────
# DATA AUGMENTATION GENERATOR
# ─────────────────────────────────────────────


def build_augmentation_generator():
    """
    Keras ImageDataGenerator with FER2013-appropriate augmentations.
    """
    try:
        from keras.preprocessing.image import ImageDataGenerator
    except ImportError:
        from tensorflow.keras.preprocessing.image import ImageDataGenerator

    return ImageDataGenerator(
        rotation_range=emotion_cfg.ROTATION_RANGE,
        width_shift_range=emotion_cfg.WIDTH_SHIFT,
        height_shift_range=emotion_cfg.HEIGHT_SHIFT,
        horizontal_flip=emotion_cfg.HORIZONTAL_FLIP,
        zoom_range=emotion_cfg.ZOOM_RANGE,
        fill_mode="nearest",
    )


# ─────────────────────────────────────────────
# CLASS WEIGHT CALCULATOR
# ─────────────────────────────────────────────


def compute_class_weights(y_train):
    """
    Compute inverse-frequency class weights to handle FER2013's
    significant class imbalance (e.g. disgusted << happy).

    Returns:
        dict {class_index: weight}
    """
    from sklearn.utils.class_weight import compute_class_weight

    weights = compute_class_weight(
        class_weight="balanced",
        classes=np.unique(y_train),
        y=y_train,
    )
    weight_dict = {int(i): float(w) for i, w in enumerate(weights)}
    logger.info("Class weights: %s", weight_dict)
    return weight_dict


# ─────────────────────────────────────────────
# EVALUATION UTILITIES
# ─────────────────────────────────────────────


def evaluate_model(model, X_test, y_test):
    """
    Run full evaluation and print:
      - Test accuracy & loss
      - Per-class classification report
      - Confusion matrix
    """
    from sklearn.metrics import classification_report, confusion_matrix

    try:
        from keras.utils import to_categorical
    except ImportError:
        from tensorflow.keras.utils import to_categorical

    logger.info("Evaluating on test set (%d samples)...", len(X_test))

    y_test_cat = to_categorical(y_test, num_classes=emotion_cfg.NUM_CLASSES)
    loss, acc, top2 = model.evaluate(X_test, y_test_cat, verbose=0)
    logger.info("Test loss=%.4f  acc=%.4f  top2_acc=%.4f", loss, acc, top2)

    y_pred_probs = model.predict(X_test, verbose=0)
    y_pred = np.argmax(y_pred_probs, axis=1)

    print("\n" + "=" * 60)
    print("CLASSIFICATION REPORT")
    print("=" * 60)
    print(classification_report(y_test, y_pred, target_names=emotion_cfg.CLASSES))

    cm = confusion_matrix(y_test, y_pred)
    print("CONFUSION MATRIX")
    print("-" * 60)
    header = "          " + "  ".join("%8s" % c[:3] for c in emotion_cfg.CLASSES)
    print(header)
    for i, row in enumerate(cm):
        row_str = "  ".join("%8d" % v for v in row)
        print("%-10s%s" % (emotion_cfg.CLASSES[i][:10], row_str))
    print("=" * 60)

    return {"loss": loss, "accuracy": acc, "top2_accuracy": top2}


def plot_training_history(history, save_path=None):
    """
    Plot accuracy and loss curves. Saves to file if save_path given.
    Silently skips if matplotlib not installed.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not installed -- skipping plot.")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    axes[0].plot(history.history["accuracy"], label="train acc")
    axes[0].plot(history.history["val_accuracy"], label="val acc")
    axes[0].set_title("Accuracy")
    axes[0].set_xlabel("Epoch")
    axes[0].legend()

    axes[1].plot(history.history["loss"], label="train loss")
    axes[1].plot(history.history["val_loss"], label="val loss")
    axes[1].set_title("Loss")
    axes[1].set_xlabel("Epoch")
    axes[1].legend()

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150)
        logger.info("Training plot saved: %s", save_path)
    else:
        plt.show()


# ─────────────────────────────────────────────
# FINE-TUNE TRANSFER LEARNING BACKBONES
# ─────────────────────────────────────────────


def unfreeze_top_layers(model, num_layers=20):
    """
    Unfreeze the top N layers of the base model for fine-tuning.
    Call after initial training with frozen base.
    """
    base = None
    for layer in model.layers:
        if hasattr(layer, "layers"):  # it's a nested model (base)
            base = layer
            break
    if base is None:
        logger.warning("No nested base model found to unfreeze.")
        return

    for layer in base.layers[-num_layers:]:
        layer.trainable = True
    logger.info("Unfroze top %d layers of %s for fine-tuning.", num_layers, base.name)


# ─────────────────────────────────────────────
# MAIN TRAINING FUNCTION
# ─────────────────────────────────────────────


def train(args):
    """
    Full training pipeline.

    Args:
        args: Namespace from argparse (or a simple object with the same attrs)
    """
    import tensorflow as tf

    try:
        from keras.utils import to_categorical
    except ImportError:
        from tensorflow.keras.utils import to_categorical

    # ── GPU config ──────────────────────────────
    gpus = tf.config.list_physical_devices("GPU")
    if gpus:
        for gpu in gpus:
            tf.config.experimental.set_memory_growth(gpu, True)
        logger.info("GPUs available: %d", len(gpus))
    else:
        logger.info("No GPU found -- training on CPU (will be slow).")

    # Set random seeds for reproducibility
    tf.random.set_seed(dataset_cfg.RANDOM_SEED)
    np.random.seed(dataset_cfg.RANDOM_SEED)

    # ── Override config from CLI args ────────────
    emotion_cfg.BACKBONE = args.backbone
    emotion_cfg.EPOCHS = args.epochs
    emotion_cfg.BATCH_SIZE = args.batch_size

    # ── Load dataset ─────────────────────────────
    if args.csv and Path(args.csv).exists():
        X_train, y_train, X_val, y_val, X_test, y_test = load_fer2013_csv(args.csv)
    elif args.data_dir and args.test_dir:
        X_train, y_train, X_val, y_val, X_test, y_test = load_image_folders(
            args.data_dir, args.test_dir
        )
    elif dataset_cfg.FER2013_PATH.exists():
        X_train, y_train, X_val, y_val, X_test, y_test = load_fer2013_csv(dataset_cfg.FER2013_PATH)
    else:
        logger.error(
            "No dataset found!\n"
            "  Option 1: Place fer2013.csv in data/\n"
            "  Option 2: Use --csv path/to/fer2013.csv\n"
            "  Option 3: Use --data_dir data/train --test_dir data/test\n"
            "  Download: https://www.kaggle.com/datasets/msambare/fer2013"
        )
        sys.exit(1)

    # One-hot encode labels
    y_train_cat = to_categorical(y_train, num_classes=emotion_cfg.NUM_CLASSES)
    y_val_cat = to_categorical(y_val, num_classes=emotion_cfg.NUM_CLASSES)

    # ── Build model ──────────────────────────────
    detector = EmotionDetector()
    model = detector.build_model()

    logger.info(
        "Model: %s | params=%s",
        model.name,
        "{:,}".format(model.count_params()),
    )

    # ── Data augmentation ────────────────────────
    aug_gen = build_augmentation_generator()
    train_gen = aug_gen.flow(
        X_train,
        y_train_cat,
        batch_size=emotion_cfg.BATCH_SIZE,
        seed=dataset_cfg.RANDOM_SEED,
    )
    steps_per_epoch = len(X_train) // emotion_cfg.BATCH_SIZE
    validation_steps = len(X_val) // emotion_cfg.BATCH_SIZE

    # ── Class weights ────────────────────────────
    class_weights = compute_class_weights(y_train) if args.class_weights else None

    # ── Phase 1: Train (base frozen for transfer models) ──
    logger.info("Phase 1: Training for %d epochs...", emotion_cfg.EPOCHS)
    history = model.fit(
        train_gen,
        steps_per_epoch=steps_per_epoch,
        epochs=emotion_cfg.EPOCHS,
        validation_data=(X_val, y_val_cat),
        validation_steps=validation_steps,
        callbacks=detector.get_callbacks(),
        class_weight=class_weights,
        verbose=1,
    )

    # ── Phase 2: Fine-tune transfer backbones ────
    if args.backbone in ("mobilenet", "resnet") and args.fine_tune:
        logger.info("Phase 2: Fine-tuning top layers...")
        unfreeze_top_layers(model, num_layers=30)
        detector._compile()  # recompile with lower LR
        model.optimizer.learning_rate.assign(emotion_cfg.LEARNING_RATE * 0.1)

        model.fit(
            train_gen,
            steps_per_epoch=steps_per_epoch,
            epochs=args.fine_tune_epochs,
            validation_data=(X_val, y_val_cat),
            callbacks=detector.get_callbacks(),
            class_weight=class_weights,
            verbose=1,
        )

    # ── Evaluate ─────────────────────────────────
    metrics = evaluate_model(model, X_test, y_test)

    # ── Save model ───────────────────────────────
    detector.save_model(emotion_cfg.MODEL_PATH)
    logger.info("Training complete. Model saved to: %s", emotion_cfg.MODEL_PATH)

    # ── Plot ─────────────────────────────────────
    if args.plot:
        plot_path = LOG_DIR / "training_curves.png"
        plot_training_history(history, save_path=str(plot_path))

    return metrics


# ─────────────────────────────────────────────
# CLI ARGUMENT PARSER
# ─────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(description="Train the Emotion-Aware AI Tutor CNN on FER2013.")

    # Dataset
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Path to fer2013.csv. Auto-detected from data/ if not given.",
    )
    parser.add_argument(
        "--data_dir",
        type=str,
        default=None,
        help="Path to training image folder (class sub-folders).",
    )
    parser.add_argument(
        "--test_dir",
        type=str,
        default=None,
        help="Path to test image folder (class sub-folders).",
    )

    # Model
    parser.add_argument(
        "--backbone",
        type=str,
        choices=["custom_cnn", "mobilenet", "resnet"],
        default="custom_cnn",
        help="CNN backbone to use (default: custom_cnn).",
    )

    # Training
    parser.add_argument(
        "--epochs",
        type=int,
        default=emotion_cfg.EPOCHS,
        help="Number of training epochs.",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=emotion_cfg.BATCH_SIZE,
        help="Mini-batch size.",
    )
    parser.add_argument(
        "--class_weights",
        action="store_true",
        default=True,
        help="Apply inverse-frequency class weights (default: on).",
    )
    parser.add_argument(
        "--no_class_weights",
        dest="class_weights",
        action="store_false",
        help="Disable class weighting.",
    )

    # Fine-tuning (transfer learning only)
    parser.add_argument(
        "--fine_tune",
        action="store_true",
        default=False,
        help="Fine-tune top layers after initial training (mobilenet/resnet only).",
    )
    parser.add_argument(
        "--fine_tune_epochs",
        type=int,
        default=10,
        help="Number of fine-tuning epochs.",
    )

    # Output
    parser.add_argument(
        "--plot",
        action="store_true",
        default=False,
        help="Save training curve plot to logs/training_curves.png.",
    )
    parser.add_argument(
        "--log_level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    return parser.parse_args()


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    train(args)
