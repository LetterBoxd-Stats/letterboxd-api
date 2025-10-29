"""
train_model.py

Enhanced version that trains both rating prediction AND like prediction models.
"""

import base64
from surprise import Dataset, Reader, SVD
from pymongo import MongoClient
import logging
from dotenv import load_dotenv
import pandas as pd
import pickle
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import numpy as np

# ──────────────────────────────────────────────
# 🔧 CONFIGURATION
# ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# MongoDB configuration
DB_URI = os.getenv("DB_URI")
DB_NAME = os.getenv("DB_NAME")
FILMS_COLLECTION = os.getenv("DB_FILMS_COLLECTION")
MODELS_COLLECTION = os.getenv("DB_MODELS_COLLECTION")

# ──────────────────────────────────────────────
# 📦 CONNECT TO DATABASE
# ──────────────────────────────────────────────
logging.info("Connecting to MongoDB...")
client = MongoClient(DB_URI)
db = client[DB_NAME]
films_col = db[FILMS_COLLECTION]

# ──────────────────────────────────────────────
# 🧹 EXTRACT USER-FILM-RATING-LIKE DATA
# ──────────────────────────────────────────────
def extract_training_data():
    """Extract both rating and like data from MongoDB"""
    rating_records = []
    like_records = []
    user_like_stats = {}
    
    cursor = films_col.find(
        {"reviews": {"$exists": True, "$ne": []}},
        {"film_id": 1, "reviews": 1, "avg_rating": 1, "like_ratio": 1}
    )

    for film in cursor:
        film_id = film.get("film_id")
        film_avg_rating = film.get("avg_rating")
        film_like_ratio = film.get("like_ratio", 0)
        
        for review in film.get("reviews", []):
            user = review.get("user")
            rating = review.get("rating")
            is_liked = review.get("is_liked", False)
            
            if user and rating:
                # For rating prediction
                rating_records.append({
                    "user_id": user,
                    "film_id": film_id,
                    "rating": float(rating)
                })
                
                # For like prediction (only if we have like data)
                if is_liked is not None:
                    like_records.append({
                        "user_id": user,
                        "film_id": film_id,
                        "rating": float(rating),
                        "is_liked": bool(is_liked),
                        "film_avg_rating": film_avg_rating or 0,
                        "film_like_ratio": film_like_ratio or 0
                    })
                    
                    # Track user like behavior
                    if user not in user_like_stats:
                        user_like_stats[user] = {"total_likes": 0, "total_reviews": 0}
                    user_like_stats[user]["total_reviews"] += 1
                    if is_liked:
                        user_like_stats[user]["total_likes"] += 1
    
    return rating_records, like_records, user_like_stats

# ──────────────────────────────────────────────
# 🧠 TRAIN RATING PREDICTION MODEL (SVD)
# ──────────────────────────────────────────────
def train_rating_model(rating_records):
    """Train the collaborative filtering model for ratings"""
    if not rating_records:
        raise ValueError("No rating records found for training")
    
    ratings_df = pd.DataFrame(rating_records)
    reader = Reader(rating_scale=(0.5, 5.0))
    data = Dataset.load_from_df(ratings_df[["user_id", "film_id", "rating"]], reader)
    trainset = data.build_full_trainset()
    
    logging.info("Training rating prediction model (SVD)...")
    model = SVD()
    model.fit(trainset)
    
    return model, ratings_df

# ──────────────────────────────────────────────
# 🧠 TRAIN LIKE PREDICTION MODEL
# ──────────────────────────────────────────────
def train_like_model(like_records, user_like_stats, rating_model, ratings_df):
    """Train a like prediction model using user behavior patterns"""
    if not like_records:
        logging.warning("No like data found. Using fallback threshold-based approach.")
        return None
    
    # Create features for like prediction
    features = []
    labels = []
    
    for record in like_records:
        user_id = record["user_id"]
        film_id = record["film_id"]
        rating = record["rating"]
        film_avg_rating = record["film_avg_rating"]
        film_like_ratio = record["film_like_ratio"]
        
        # User behavior features
        user_stats = user_like_stats.get(user_id, {"total_likes": 0, "total_reviews": 0})
        user_like_rate = user_stats["total_likes"] / max(user_stats["total_reviews"], 1)
        
        # Get predicted rating from the SVD model
        try:
            pred_rating = rating_model.predict(user_id, film_id).est
        except:
            pred_rating = film_avg_rating  # Fallback to film average
        
        # Feature engineering
        feature_vector = [
            rating,                    # Actual rating
            pred_rating,               # Predicted rating
            film_avg_rating,           # Film's average rating
            film_like_ratio,           # Film's like ratio
            user_like_rate,            # User's historical like rate
            user_stats["total_reviews"], # User's review count
            abs(rating - film_avg_rating),  # Rating deviation from average
            abs(pred_rating - film_avg_rating),  # Predicted rating deviation
        ]
        
        features.append(feature_vector)
        labels.append(record["is_liked"])
    
    # Train classifier
    X = np.array(features)
    y = np.array(labels)
    
    if len(np.unique(y)) < 2:
        logging.warning("Insufficient like/dislike data for training classifier")
        return None
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    logging.info("Training like prediction model (Random Forest)...")
    like_model = RandomForestClassifier(n_estimators=100, random_state=42)
    like_model.fit(X_train, y_train)
    
    # Evaluate
    y_pred = like_model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logging.info(f"Like prediction model accuracy: {accuracy:.3f}")
    
    return like_model

# ──────────────────────────────────────────────
# 💾 SAVE MODELS
# ──────────────────────────────────────────────
def save_models(rating_model, like_model, models_collection):
    """Save both models to MongoDB"""
    model_data = {
        "name": "predictor",
        "last_updated": datetime.utcnow()
    }
    
    # Save rating model
    rating_model_bytes = pickle.dumps(rating_model)
    model_data["rating_model_b64"] = base64.b64encode(rating_model_bytes).decode("utf-8")
    
    # Save like model if available
    if like_model:
        like_model_bytes = pickle.dumps(like_model)
        model_data["like_model_b64"] = base64.b64encode(like_model_bytes).decode("utf-8")
        model_data["has_like_model"] = True
    else:
        model_data["has_like_model"] = False
        logging.info("Using fallback like prediction (threshold-based)")
    
    models_collection.replace_one(
        {"name": "predictor"},
        model_data,
        upsert=True
    )

# ──────────────────────────────────────────────
# 🚀 MAIN TRAINING PIPELINE
# ──────────────────────────────────────────────
def main():
    logging.info("Starting model training pipeline...")
    
    # Extract data
    rating_records, like_records, user_like_stats = extract_training_data()
    logging.info(f"Extracted {len(rating_records)} rating records and {len(like_records)} like records")
    
    # Train rating model
    rating_model, ratings_df = train_rating_model(rating_records)
    
    # Train like model
    like_model = train_like_model(like_records, user_like_stats, rating_model, ratings_df)
    
    # Save models
    models_col = db[MODELS_COLLECTION]
    save_models(rating_model, like_model, models_col)
    
    logging.info("✅ Model training completed successfully!")

if __name__ == "__main__":
    main()