"""
Trains a small neural network (MLP) to classify security events into
one of 6 attack categories.

Pipeline:
    text  →  TF-IDF vector  →  PyTorch MLP  →  softmax over 6 classes

Artifacts produced:
    ml/models/event_classifier.pt       (model weights)
    ml/models/tfidf_vectorizer.pkl      (fitted vectorizer)
    ml/results/metrics.json             (accuracy, F1, per-class report)
    ml/results/confusion_matrix.png     (image for slides)
    ml/results/training_curves.png      (loss & accuracy per epoch)
"""

import json
import pickle
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no GUI — save figures to file
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, TensorDataset

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "events_dataset.csv"
MODEL_DIR = ROOT / "models"
RESULTS_DIR = ROOT / "results"
MODEL_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

SEED = 42
TEST_SIZE = 0.20
TFIDF_MAX_FEATURES = 3000
EPOCHS = 30
BATCH_SIZE = 16
LEARNING_RATE = 0.001
HIDDEN1 = 128
HIDDEN2 = 64
DROPOUT = 0.3

random_state = SEED
torch.manual_seed(SEED)
np.random.seed(SEED)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[device] {device}")


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

print("\n[1/6] Loading dataset...")
df = pd.read_csv(DATA_FILE)
print(f"  rows: {len(df)}")
print(f"  classes: {sorted(df['label'].unique())}")

# Map labels to indices
classes = sorted(df["label"].unique())
class_to_idx = {c: i for i, c in enumerate(classes)}
idx_to_class = {i: c for c, i in class_to_idx.items()}
df["label_idx"] = df["label"].map(class_to_idx)

print(f"  label map: {class_to_idx}")


# ---------------------------------------------------------------------------
# 2. Split
# ---------------------------------------------------------------------------

print("\n[2/6] Splitting train/test...")
X_train_text, X_test_text, y_train, y_test = train_test_split(
    df["text"].values,
    df["label_idx"].values,
    test_size=TEST_SIZE,
    random_state=random_state,
    stratify=df["label_idx"].values,
)
print(f"  train: {len(X_train_text)}  |  test: {len(X_test_text)}")


# ---------------------------------------------------------------------------
# 3. Vectorize (TF-IDF)
# ---------------------------------------------------------------------------

print("\n[3/6] Vectorizing with TF-IDF...")
vectorizer = TfidfVectorizer(
    max_features=TFIDF_MAX_FEATURES,
    ngram_range=(1, 2),
    lowercase=True,
)
X_train = vectorizer.fit_transform(X_train_text).toarray().astype(np.float32)
X_test = vectorizer.transform(X_test_text).toarray().astype(np.float32)
print(f"  feature dim: {X_train.shape[1]}")

# Save vectorizer — needed at inference time
with (MODEL_DIR / "tfidf_vectorizer.pkl").open("wb") as f:
    pickle.dump(vectorizer, f)


# ---------------------------------------------------------------------------
# 4. Build model
# ---------------------------------------------------------------------------

print("\n[4/6] Building MLP...")

class EventClassifier(nn.Module):
    def __init__(self, input_dim, num_classes):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, HIDDEN1),
            nn.ReLU(),
            nn.Dropout(DROPOUT),
            nn.Linear(HIDDEN1, HIDDEN2),
            nn.ReLU(),
            nn.Dropout(DROPOUT),
            nn.Linear(HIDDEN2, num_classes),
        )

    def forward(self, x):
        return self.net(x)


model = EventClassifier(X_train.shape[1], len(classes)).to(device)
print(model)


# ---------------------------------------------------------------------------
# 5. Train
# ---------------------------------------------------------------------------

print("\n[5/6] Training...")
X_train_t = torch.tensor(X_train, dtype=torch.float32)
y_train_t = torch.tensor(y_train, dtype=torch.long)
X_test_t = torch.tensor(X_test, dtype=torch.float32)
y_test_t = torch.tensor(y_test, dtype=torch.long)

train_ds = TensorDataset(X_train_t, y_train_t)
train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=LEARNING_RATE)

train_losses = []
train_accs = []
test_losses = []
test_accs = []

for epoch in range(1, EPOCHS + 1):
    # ---- train ----
    model.train()
    epoch_loss = 0.0
    correct = 0
    total = 0
    for xb, yb in train_loader:
        xb, yb = xb.to(device), yb.to(device)
        optimizer.zero_grad()
        out = model(xb)
        loss = criterion(out, yb)
        loss.backward()
        optimizer.step()
        epoch_loss += loss.item() * xb.size(0)
        preds = out.argmax(dim=1)
        correct += (preds == yb).sum().item()
        total += xb.size(0)
    train_losses.append(epoch_loss / total)
    train_accs.append(correct / total)

    # ---- eval ----
    model.eval()
    with torch.no_grad():
        out = model(X_test_t.to(device))
        loss = criterion(out, y_test_t.to(device))
        test_losses.append(loss.item())
        preds = out.argmax(dim=1).cpu().numpy()
        test_accs.append(accuracy_score(y_test, preds))

    if epoch % 5 == 0 or epoch == 1:
        print(f"  epoch {epoch:>2}/{EPOCHS}  "
              f"train_loss={train_losses[-1]:.4f}  train_acc={train_accs[-1]:.4f}  "
              f"test_loss={test_losses[-1]:.4f}  test_acc={test_accs[-1]:.4f}")


# ---------------------------------------------------------------------------
# 6. Evaluate + save artifacts
# ---------------------------------------------------------------------------

print("\n[6/6] Evaluating...")
model.eval()
with torch.no_grad():
    logits = model(X_test_t.to(device)).cpu().numpy()
y_pred = logits.argmax(axis=1)

acc = accuracy_score(y_test, y_pred)
macro_f1 = f1_score(y_test, y_pred, average="macro")
report = classification_report(
    y_test, y_pred,
    target_names=classes,
    digits=4,
)
cm = confusion_matrix(y_test, y_pred)

print(f"\n  Accuracy  : {acc:.4f}")
print(f"  Macro F1  : {macro_f1:.4f}")
print("\n" + report)

# --- metrics.json ---
metrics = {
    "accuracy": float(acc),
    "macro_f1": float(macro_f1),
    "classes": classes,
    "classification_report": classification_report(
        y_test, y_pred, target_names=classes, digits=4, output_dict=True
    ),
}
with (RESULTS_DIR / "metrics.json").open("w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)
print(f"  → {RESULTS_DIR / 'metrics.json'}")

# --- confusion matrix image ---
fig, ax = plt.subplots(figsize=(7, 6))
im = ax.imshow(cm, cmap="Blues")
ax.set_xticks(range(len(classes)))
ax.set_yticks(range(len(classes)))
ax.set_xticklabels(classes, rotation=45, ha="right")
ax.set_yticklabels(classes)
ax.set_xlabel("Predicted")
ax.set_ylabel("True")
ax.set_title(f"Confusion Matrix — Accuracy {acc:.2%}")
for i in range(len(classes)):
    for j in range(len(classes)):
        ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                color="white" if cm[i, j] > cm.max() / 2 else "black")
fig.colorbar(im)
fig.tight_layout()
fig.savefig(RESULTS_DIR / "confusion_matrix.png", dpi=120)
plt.close(fig)
print(f"  → {RESULTS_DIR / 'confusion_matrix.png'}")

# --- training curves ---
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
axes[0].plot(train_losses, label="train")
axes[0].plot(test_losses, label="test")
axes[0].set_title("Loss per epoch")
axes[0].set_xlabel("Epoch")
axes[0].set_ylabel("CrossEntropy")
axes[0].legend()
axes[1].plot(train_accs, label="train")
axes[1].plot(test_accs, label="test")
axes[1].set_title("Accuracy per epoch")
axes[1].set_xlabel("Epoch")
axes[1].set_ylabel("Accuracy")
axes[1].legend()
fig.tight_layout()
fig.savefig(RESULTS_DIR / "training_curves.png", dpi=120)
plt.close(fig)
print(f"  → {RESULTS_DIR / 'training_curves.png'}")

# --- model weights ---
torch.save(
    {
        "state_dict": model.state_dict(),
        "input_dim": X_train.shape[1],
        "classes": classes,
        "class_to_idx": class_to_idx,
        "hidden1": HIDDEN1,
        "hidden2": HIDDEN2,
        "dropout": DROPOUT,
    },
    MODEL_DIR / "event_classifier.pt",
)
print(f"  → {MODEL_DIR / 'event_classifier.pt'}")

print("\n Training complete.")