import pandas as pd
from stop_words import get_stop_words
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from collections import Counter
from nltk.tokenize import word_tokenize
import nltk
nltk.download('punkt')

import re


class TextCleaner:
    def __init__(self, language='en'):
        # Get a list of English stop words
        self.stop_words = get_stop_words(language)

    def _clean(self, text: str) -> str | None:
        # Convert text to lowercase
        text = text.lower()
        # Remove special characters and digits
        text = re.sub(r'[^a-zA-Z0-9\s.,!?-]', '', text)

        # Optionally, remove stop words
        text_tokens = text.split()
        filtered_text = ' '.join([word for word in text_tokens if word not in self.stop_words and len(word) > 1])
        if len(filtered_text) == 0:
            return None
        return filtered_text

    def apply_cleaner(self, text_series: pd.Series) -> pd.Series:
        return text_series.apply(self._clean)

    def set_target(self, target: pd.Series) -> pd.Series:
        res = target.replace({'negative': 0, 'neutral': 1, 'positive': 2})
        return res

# Tokenization and Vocabulary Building
def build_vocab(data):
    counter = Counter()
    for text in data:
        tokens = text.lower().split()
        counter.update(tokens)
    vocab = {word: i + 1 for i, (word, _) in enumerate(counter.items())}
    vocab['<pad>'] = 0
    return vocab



class SentimentDataset(Dataset):
    def __init__(self, texts, labels, vocab):
        self.texts = [self.encode(text, vocab) for text in texts]
        self.labels = labels

    def encode(self, text, vocab):
        tokens = word_tokenize(text.lower())
        return [vocab.get(token, 0) for token in tokens]

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return torch.tensor(self.texts[idx], dtype=torch.long), torch.tensor(self.labels[idx], dtype=torch.long)


# Multi-Class Feed-Forward Neural Network
class SentimentModel(nn.Module):
    def __init__(self, vocab_size):
        super(SentimentModel, self).__init__()
        self.embedding = nn.Embedding(vocab_size, 50)  # 50-dimensional embeddings
        self.fc = nn.Linear(50, 3)  # Output layer for 3 classes

    def forward(self, x):
        x = self.embedding(x)
        x = torch.mean(x, dim=1)  # Average embeddings
        x = self.fc(x)
        return x


if __name__ == '__main__':
    df_train = pd.read_csv('MELD.Raw/train/train_sent_emo.csv')
    df_dev = pd.read_csv('MELD.Raw/dev_sent_emo.csv')
    df_test = pd.read_csv('MELD.Raw/test_sent_emo.csv')
    text_cleaner = TextCleaner()
    # clean stop words and special characters
    df_train['tokens'] = text_cleaner.apply_cleaner(df_train['Utterance'])
    df_dev['tokens'] = text_cleaner.apply_cleaner(df_dev['Utterance'])
    df_test['tokens'] = text_cleaner.apply_cleaner(df_test['Utterance'])
    df_train = df_train.dropna(subset=['tokens'])
    df_dev = df_dev.dropna(subset=['tokens'])
    df_test = df_test.dropna(subset=['tokens'])
    # set target
    df_train['labels'] = text_cleaner.set_target(df_train['Sentiment'])
    df_dev['labels'] = text_cleaner.set_target(df_dev['Sentiment'])
    df_test['labels'] = text_cleaner.set_target(df_test['Sentiment'])

    # Preparing datasets
    vocab = build_vocab(df_train['tokens'])
    train_dataset = SentimentDataset(df_train['tokens'], df_train['labels'], vocab)
    dev_dataset = SentimentDataset(df_dev['tokens'], df_dev['labels'], vocab)
    test_dataset = SentimentDataset(df_test['tokens'], df_test['labels'], vocab)

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
    dev_loader = DataLoader(dev_dataset, batch_size=32, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

    # Model, Loss, and Optimizer
    model = SentimentModel(len(vocab))
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)

    # Training Loop
    for epoch in range(10):
        for inputs, targets in train_loader:
            optimizer.zero_grad()
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            loss.backward()
            optimizer.step()
        print(f"Epoch {epoch + 1}, Loss: {loss.item()}")
