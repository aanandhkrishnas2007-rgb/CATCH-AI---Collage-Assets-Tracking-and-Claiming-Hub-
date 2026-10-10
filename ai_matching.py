"""
CATCH — AI Matching Engine

Combines three signals into a single match score:
  1. Image similarity   (OpenCV color-histogram comparison)
  2. Text similarity     (TF-IDF + cosine similarity over description/unique marks)
  3. Attribute similarity (category / brand / color exact-ish matching)

Final score is a weighted blend, expressed as a percentage (0-100).
This intentionally avoids heavyweight dependencies (FAISS, sentence-transformers)
so it installs and runs fast — accuracy is still meaningful for a real demo.
"""

import os
import cv2
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Weights for the final blended score
WEIGHT_IMAGE = 0.35
WEIGHT_TEXT = 0.35
WEIGHT_ATTRIBUTES = 0.30


def _load_image_histogram(image_path):
    """Load an image and compute a normalized HSV color histogram."""
    if not image_path or not os.path.exists(image_path):
        return None
    img = cv2.imread(image_path)
    if img is None:
        return None
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
    return hist


def image_similarity(path_a, path_b):
    """Returns similarity 0-100 between two images using histogram correlation."""
    hist_a = _load_image_histogram(path_a)
    hist_b = _load_image_histogram(path_b)
    if hist_a is None or hist_b is None:
        return 0.0
    score = cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL)
    score = max(0.0, min(1.0, score))  # clamp to [0, 1]
    return round(score * 100, 2)


def text_similarity(text_a, text_b):
    """Returns similarity 0-100 between two text blobs using TF-IDF cosine similarity."""
    text_a = (text_a or "").strip()
    text_b = (text_b or "").strip()
    if not text_a or not text_b:
        return 0.0
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform([text_a, text_b])
        sim = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return round(float(sim) * 100, 2)
    except ValueError:
        # Happens if both strings are entirely stopwords / empty after vectorizing
        return 0.0


def attribute_similarity(lost_item, found_item):
    """Compares category, brand, and color for exact/partial matches. Returns 0-100."""
    score = 0.0
    weight_per_field = 100 / 3

    if lost_item.category and found_item.category:
        if lost_item.category.strip().lower() == found_item.category.strip().lower():
            score += weight_per_field

    if lost_item.brand and found_item.brand:
        if lost_item.brand.strip().lower() == found_item.brand.strip().lower():
            score += weight_per_field
    elif not lost_item.brand and not found_item.brand:
        score += weight_per_field * 0.5  # neither specified brand — partial credit

    if lost_item.color and found_item.color:
        if lost_item.color.strip().lower() == found_item.color.strip().lower():
            score += weight_per_field

    return round(score, 2)


def compute_match_score(lost_item, found_item, upload_folder):
    """
    Computes the full blended match score between a LostItem and a FoundItem.
    Returns a dict with overall score plus the individual component scores.
    """
    lost_image_path = (
        os.path.join(upload_folder, lost_item.image_path) if lost_item.image_path else None
    )
    found_image_path = (
        os.path.join(upload_folder, found_item.image_path) if found_item.image_path else None
    )

    img_score = image_similarity(lost_image_path, found_image_path)

    combined_lost_text = " ".join(filter(None, [
        lost_item.item_name, lost_item.description, lost_item.unique_marks
    ]))
    combined_found_text = " ".join(filter(None, [
        found_item.item_name, found_item.description, found_item.unique_marks
    ]))
    txt_score = text_similarity(combined_lost_text, combined_found_text)

    attr_score = attribute_similarity(lost_item, found_item)

    overall = (
        img_score * WEIGHT_IMAGE
        + txt_score * WEIGHT_TEXT
        + attr_score * WEIGHT_ATTRIBUTES
    )

    return {
        "overall": round(overall, 2),
        "image_score": img_score,
        "text_score": txt_score,
        "attribute_score": attr_score,
    }


def find_best_matches(lost_item, found_items, upload_folder, top_n=5, min_score=30.0):
    """
    Given one lost item and a list of candidate found items,
    returns the top N matches sorted by overall score descending.
    """
    results = []
    for found_item in found_items:
        if found_item.status != "open":
            continue
        scores = compute_match_score(lost_item, found_item, upload_folder)
        if scores["overall"] >= min_score:
            results.append({"found_item": found_item, **scores})

    results.sort(key=lambda r: r["overall"], reverse=True)
    return results[:top_n]
