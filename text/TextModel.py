from typing import List

from sklearn.metrics import accuracy_score
import librosa
import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV
from stop_words import get_stop_words

import nltk

import utils

nltk.download('punkt')
import gensim.downloader as api
import re
import xgboost as xgb
import statsmodels.api as sm


class TextCleaner:
    def __init__(self, language='en'):
        # Get a list of English stop words
        self.stop_words = get_stop_words(language)

    def _clean(self, text: str) -> str | None:
        # Convert text to lowercase
        text = text.lower()
        # Remove special characters and digits
        try:
            text = text.encode('latin1').decode('cp1252')
        except UnicodeEncodeError:
            pass
        text = re.sub(r'[^a-zA-Z0-9\s.,!?-]', '', text)

        # Optionally, remove stop words
        text_tokens = text.split()
        filtered_text = ' '.join([word for word in text_tokens if word not in self.stop_words and len(word) > 1])
        if len(filtered_text) == 0:
            return None
        return filtered_text

    def apply_cleaner(self, text_series: pd.Series) -> pd.Series:
        return text_series.apply(self._clean)


def extract_features(waveform, sr):
    """
    Calculate various spectral features and return them in a dictionary.
    """
    # Basic spectral features
    spectral_centroid = librosa.feature.spectral_centroid(y=waveform, sr=sr)[0]
    spectral_bandwidth = librosa.feature.spectral_bandwidth(y=waveform, sr=sr)[0]
    spectral_flatness = librosa.feature.spectral_flatness(y=waveform)[0]
    spectral_rolloff = librosa.feature.spectral_rolloff(y=waveform, sr=sr)[0]
    rms_energy = librosa.feature.rms(y=waveform)[0]
    zcr = librosa.feature.zero_crossing_rate(waveform)[0]
    mfccs = librosa.feature.mfcc(y=waveform, sr=sr)
    chroma = librosa.feature.chroma_stft(y=waveform, sr=sr)

    # Initialize the feature dictionary
    features = {
        'centroid_mean': np.mean(spectral_centroid),
        'bandwidth_mean': np.mean(spectral_bandwidth),
        'flatness_mean': np.mean(spectral_flatness),
        'rolloff_mean': np.mean(spectral_rolloff),
        'rms_energy_mean': np.mean(rms_energy),
        'zcr_mean': np.mean(zcr)
    }

    # Adding MFCCs and Chroma features
    for i in range(mfccs.shape[0]):  # Assuming MFCCs are returned with shape (n_mfcc, t)
        features[f'mfccs_mean_{i}'] = np.mean(mfccs[i, :])

    for i in range(chroma.shape[0]):  # Assuming Chroma features are returned with shape (n_chroma, t)
        features[f'chroma_mean_{i}'] = np.mean(chroma[i, :])

    return features


def sentence_to_vec(df, embedding_model):
    vec_list = []
    for index, row in df.iterrows():
        sentence = row['tokens']  # Directly using the 'tokens' column
        word_vectors = []
        for word in sentence.split():
            try:
                word_vectors.append(embedding_model[word])
            except KeyError:
                continue  # Skip words not in the vocabulary
        if word_vectors:
            vec_list.append(np.mean(word_vectors, axis=0))
        else:
            vec_list.append(np.zeros(100))  # Assuming 100 dimensional embeddings

    # Create a DataFrame from the list of vectors and preserve the original index
    vec_df = pd.DataFrame(vec_list, index=df.index)
    return vec_df


def clean_stop_words_and_special_characters_and_set_target(df: pd.DataFrame):
    text_cleaner = TextCleaner()
    df['tokens'] = text_cleaner.apply_cleaner(df['Utterance'])
    df = utils.set_target(df)
    df = df.dropna(subset=['tokens'])
    return df


class TextModel:
    def __init__(self):
        self.glove_model = api.load("glove-wiki-gigaword-100")

    def preprocessing(self, df):
        df = clean_stop_words_and_special_characters_and_set_target(df)
        df = utils.file_key_generator(df)
        df = df.set_index('file_key')
        sentence_vectors = sentence_to_vec(df, self.glove_model)
        sentence_vectors.columns = [f'text_feature_{i + 1}' for i in range(len(sentence_vectors.columns))]
        return sentence_vectors, df['label']
