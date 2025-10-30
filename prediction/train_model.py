"""
train_model.py

Enhanced version using XGBoost for both rating prediction AND like prediction models.
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
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, mean_squared_error
import numpy as np
from collections import defaultdict
import xgboost as xgb

# ──────────────────────────────────────────────
# 🔧 CONFIGURATION
# ──────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

# MongoDB configuration
DB_URI = os.getenv("DB_URI")
DB_NAME = os.getenv("DB_NAME")
FILMS_COLLECTION = os.getenv("DB_FILMS_COLLECTION")
USERS_COLLECTION = os.getenv("DB_USERS_COLLECTION")
MODELS_COLLECTION = os.getenv("DB_MODELS_COLLECTION")

# ──────────────────────────────────────────────
# 📦 CONNECT TO DATABASE
# ──────────────────────────────────────────────
logging.info("Connecting to MongoDB...")
client = MongoClient(DB_URI)
db = client[DB_NAME]
films_col = db[FILMS_COLLECTION]
users_col = db[USERS_COLLECTION]

# ──────────────────────────────────────────────
# 🧹 EXTRACT ENHANCED TRAINING DATA
# ──────────────────────────────────────────────
def extract_enhanced_training_data():
    """Extract comprehensive training data with user stats and film metadata"""
    rating_records = []
    like_records = []
    
    # Pre-load all users data for quick access
    logging.info("Loading user statistics...")
    users_data = {}
    for user in users_col.find():
        username = user.get("username")
        users_data[username] = user.get("stats", {})
    
    # Process films and their reviews
    cursor = films_col.find(
        {"reviews": {"$exists": True, "$ne": []}},
        {"film_id": 1, "film_title": 1, "avg_rating": 1, "like_ratio": 1, 
         "metadata": 1, "reviews": 1, "num_ratings": 1, "num_likes": 1}
    )

    for film in cursor:
        film_id = film.get("film_id")
        film_reviews = film.get("reviews", [])
        film_avg_rating = film.get("avg_rating", 0)
        film_like_ratio = film.get("like_ratio", 0)
        film_num_ratings = film.get("num_ratings", 0)
        film_num_likes = film.get("num_likes", 0)
        metadata = film.get("metadata", {})

        # Film metadata
        film_genres = metadata.get("genres", [])
        film_runtime = metadata.get("runtime", 0)
        film_year = metadata.get("year", 0)
        film_letterboxd_avg = metadata.get("avg_rating", 0)

        for review in film_reviews:
            user = review.get("user")
            rating = review.get("rating")
            is_liked = review.get("is_liked", False)

            if user and rating and user in users_data:
                user_stats = users_data[user]

                # --- Compute leave-one-out film aggregates ---
                other_reviews = [r for r in film_reviews if r.get("user") != user and r.get("rating") is not None]
                if other_reviews:
                    other_ratings = [float(r["rating"]) for r in other_reviews]
                    other_likes = [r.get("is_liked", False) for r in other_reviews]
                    film_avg_rating_excl_user = sum(other_ratings) / len(other_ratings)
                    film_like_ratio_excl_user = sum(1 for l in other_likes if l) / len(other_likes)
                else:
                    # Fallback to global film stats
                    film_avg_rating_excl_user = film_avg_rating
                    film_like_ratio_excl_user = film_like_ratio

                # --- Compute leave-one-out user aggregates ---
                user_num_ratings_full = user_stats.get("num_ratings", 1)
                user_num_likes_full = user_stats.get("num_likes", 0)

                user_num_ratings_excl = max(1, user_num_ratings_full - 1)
                user_num_likes_excl = max(0, user_num_likes_full - (1 if is_liked else 0))

                if user_num_ratings_excl > 0:
                    user_avg_rating_excl_film = (
                        (user_stats.get("avg_rating", 0) * user_num_ratings_full - float(rating))
                        / user_num_ratings_excl
                    )
                    user_like_ratio_excl_film = user_num_likes_excl / user_num_ratings_excl
                else:
                    user_avg_rating_excl_film = user_stats.get("avg_rating", 0)
                    user_like_ratio_excl_film = user_stats.get("like_ratio", 0)

                # --- Base feature set shared by both rating & like models ---
                base_features = {
                    "user_id": user,
                    "film_id": film_id,
                    "rating": float(rating),

                    # User-level
                    "user_avg_rating": user_avg_rating_excl_film,
                    "user_stdev_rating": user_stats.get("stdev_rating", 1.0),
                    "user_like_ratio": user_like_ratio_excl_film,
                    "user_num_ratings": user_num_ratings_excl,
                    "user_num_likes": user_num_likes_excl,
                    "user_median_rating": user_stats.get("median_rating", 3.0),

                    # Film-level
                    "film_avg_rating": film_avg_rating_excl_user,
                    "film_like_ratio": film_like_ratio_excl_user,
                    "film_num_ratings": film_num_ratings,
                    "film_letterboxd_avg": film_letterboxd_avg,
                    "film_runtime": film_runtime,
                    "film_year": film_year,

                    # Genre compatibility
                    **get_genre_compatibility_features(user_stats, film_genres),

                    # Derived numeric features
                    "user_film_rating_diff": float(rating) - user_avg_rating_excl_film,
                    "film_user_avg_diff": film_avg_rating_excl_user - user_avg_rating_excl_film,
                }

                # --- Rating model record ---
                rating_records.append(base_features.copy())

                # --- Like model record ---
                if is_liked is not None:
                    like_record = base_features.copy()
                    like_record["is_liked"] = bool(is_liked)
                    like_record.update({
                        "rating_above_user_avg": float(rating) > user_avg_rating_excl_film,
                        "rating_above_film_avg": float(rating) > film_avg_rating_excl_user,
                        "high_rated_film": film_avg_rating_excl_user >= 4.0,
                    })
                    like_records.append(like_record)

    
    return rating_records, like_records, users_data

def get_genre_compatibility_features(user_stats, film_genres):
    """Calculate genre compatibility features between user and film"""
    genre_stats = user_stats.get("genre_stats", {})
    
    features = {}
    genre_matches = []
    avg_genre_ratings = []
    genre_counts = []
    
    for genre in film_genres:
        if genre in genre_stats:
            genre_data = genre_stats[genre]
            genre_rating = genre_data.get("avg_rating")
            genre_count = genre_data.get("count", 0)
            
            if genre_rating is not None:
                genre_matches.append(genre_rating)
                avg_genre_ratings.append(genre_rating)
                genre_counts.append(genre_count)
    
    # Genre compatibility metrics
    if genre_matches:
        features["max_genre_rating"] = max(genre_matches)
        features["min_genre_rating"] = min(genre_matches)
        features["avg_genre_rating"] = sum(genre_matches) / len(genre_matches)
        features["genre_rating_std"] = np.std(genre_matches) if len(genre_matches) > 1 else 0
        features["total_genre_watches"] = sum(genre_counts)
        features["genre_coverage"] = len(genre_matches) / len(film_genres) if film_genres else 0
    else:
        # Default values when no genre match
        features.update({
            "max_genre_rating": user_stats.get("avg_rating", 3.0),
            "min_genre_rating": user_stats.get("avg_rating", 3.0),
            "avg_genre_rating": user_stats.get("avg_rating", 3.0),
            "genre_rating_std": user_stats.get("stdev_rating", 1.0),
            "total_genre_watches": 0,
            "genre_coverage": 0
        })
    
    return features

# ──────────────────────────────────────────────
# 🧠 TRAIN XGBOOST RATING PREDICTION MODEL
# ──────────────────────────────────────────────
def train_xgboost_rating_model(rating_records):
    """Train XGBoost model for rating prediction with better spread"""
    if not rating_records:
        raise ValueError("No rating records found for training")
    
    ratings_df = pd.DataFrame(rating_records)
    
    # Define feature columns (excluding target and IDs)
    feature_columns = [
        'user_avg_rating', 'user_stdev_rating', 'user_like_ratio', 'user_num_ratings',
        'user_median_rating', 'film_avg_rating', 'film_like_ratio', 'film_num_ratings',
        'film_letterboxd_avg', 'film_runtime', 'film_year', 'max_genre_rating',
        'min_genre_rating', 'avg_genre_rating', 'genre_rating_std', 'total_genre_watches',
        'genre_coverage'
    ]
    
    # Prepare features and target
    X = ratings_df[feature_columns].fillna(0)
    y = ratings_df['rating']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    print(f"\n📊 TRAINING DATA STATISTICS:")
    print(f"Training samples: {len(X_train):,}")
    print(f"Test samples: {len(X_test):,}")
    print(f"Target mean: {y_train.mean():.3f}, std: {y_train.std():.3f}")
    print(f"Target range: [{y_train.min():.1f}, {y_train.max():.1f}]")
    
    # Train XGBoost model with parameters for better spread
    logging.info("Training XGBoost rating prediction model...")
    
    rating_model = xgb.XGBRegressor(
        # Model architecture
        n_estimators=200,
        max_depth=8,
        learning_rate=0.1,
        
        # Regularization (lower for more spread)
        reg_alpha=0.1,      # L1 regularization
        reg_lambda=0.1,     # L2 regularization (LOWER for more spread)
        
        # Tree construction
        min_child_weight=3,
        gamma=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        
        # Training
        random_state=42,
        early_stopping_rounds=20,
        eval_metric='rmse'
    )
    
    # Train with validation set
    rating_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    
    # Evaluate
    y_pred = rating_model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    
    print(f"\n🎯 RATING MODEL PERFORMANCE:")
    print(f"RMSE: {rmse:.3f}")
    print(f"MSE: {mse:.3f}")
    print(f"Predictions - Mean: {y_pred.mean():.3f}, Std: {y_pred.std():.3f}")
    print(f"Predictions range: [{y_pred.min():.2f}, {y_pred.max():.2f}]")
    print(f"Spread ratio: {y_pred.std() / y_train.std():.2f}")
    
    # Feature importance
    importance_scores = rating_model.feature_importances_
    feature_importance_df = pd.DataFrame({
        'feature': feature_columns,
        'importance': importance_scores
    }).sort_values('importance', ascending=False)
    
    print(f"\n📊 FEATURE IMPORTANCE (Top 10):")
    for idx, row in feature_importance_df.head(10).iterrows():
        print(f"  {row['feature']:.<25} {row['importance']:.4f}")
    
    return {
        'model': rating_model,
        'feature_columns': feature_columns,
        'feature_importance': feature_importance_df,
        'performance': {
            'rmse': rmse,
            'mse': mse,
            'pred_mean': y_pred.mean(),
            'pred_std': y_pred.std(),
            'train_std': y_train.std()
        }
    }

# ──────────────────────────────────────────────
# 🧠 TRAIN XGBOOST LIKE PREDICTION MODEL
# ──────────────────────────────────────────────
def train_xgboost_like_model(like_records, rating_model, users_data):
    """Train XGBoost classifier for like prediction"""
    if not like_records:
        logging.warning("No like data found. Using fallback threshold-based approach.")
        return None
    
    like_df = pd.DataFrame(like_records)
    
    # Prepare features for like prediction
    features = []
    labels = []
    
    # Feature names for like prediction
    like_feature_names = [
        'actual_rating',
        'user_avg_rating', 
        'film_avg_rating',
        'user_like_ratio',
        'film_like_ratio',
        'avg_genre_rating',
        'genre_coverage',
        'personal_rating_deviation',
        'community_rating_deviation',
        'rating_above_user_avg',
        'rating_above_film_avg',
        'high_rated_film',
        'user_rating_consistency'
    ]
    
    for _, record in like_df.iterrows():
        user_id = record["user_id"]
        user_stats = users_data.get(user_id, {})
        
        # Create feature vector for like prediction
        feature_vector = [
            record['rating'],                                    # actual_rating
            record['user_avg_rating'],                          # user_avg_rating
            record['film_avg_rating'],                          # film_avg_rating
            record['user_like_ratio'],                          # user_like_ratio
            record['film_like_ratio'],                          # film_like_ratio
            record['avg_genre_rating'],                         # avg_genre_rating
            record['genre_coverage'],                           # genre_coverage
            abs(record['rating'] - record['user_avg_rating']),  # personal_rating_deviation
            abs(record['rating'] - record['film_avg_rating']),  # community_rating_deviation
            float(record['rating_above_user_avg']),             # rating_above_user_avg
            float(record['rating_above_film_avg']),             # rating_above_film_avg
            float(record['high_rated_film']),                   # high_rated_film
            user_stats.get("mean_abs_diff", 0),                 # user_rating_consistency
        ]
        
        features.append(feature_vector)
        labels.append(record['is_liked'])
    
    # Prepare data
    X = np.array(features)
    y = np.array(labels)
    
    if len(np.unique(y)) < 2:
        logging.warning("Insufficient like/dislike data for training classifier")
        return None
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    print(f"\n📊 LIKE PREDICTION DATA:")
    print(f"Training samples: {len(X_train):,} (Likes: {y_train.sum():,}, Ratio: {y_train.mean():.3f})")
    print(f"Test samples: {len(X_test):,} (Likes: {y_test.sum():,}, Ratio: {y_test.mean():.3f})")
    
    # Train XGBoost classifier
    logging.info("Training XGBoost like prediction model...")
    
    like_model = xgb.XGBClassifier(
        # Model architecture
        n_estimators=150,
        max_depth=6,
        learning_rate=0.1,
        
        # Regularization
        reg_alpha=0.1,
        reg_lambda=0.1,
        
        # Tree construction
        min_child_weight=5,
        gamma=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        
        # For classification
        objective='binary:logistic',
        eval_metric='logloss',
        random_state=42,
        early_stopping_rounds=20,
        use_label_encoder=False
    )
    
    # Train with validation set
    like_model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )
    
    # Evaluate
    y_pred = like_model.predict(X_test)
    y_pred_proba = like_model.predict_proba(X_test)[:, 1]
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n❤️  LIKE MODEL PERFORMANCE:")
    print(f"Accuracy: {accuracy:.3f}")
    print(f"Prediction distribution:")
    print(f"  Like probability mean: {y_pred_proba.mean():.3f}")
    print(f"  Like probability std: {y_pred_proba.std():.3f}")
    print(f"  Like probability range: [{y_pred_proba.min():.3f}, {y_pred_proba.max():.3f}]")
    
    # Feature importance
    like_importance_scores = like_model.feature_importances_
    like_importance_df = pd.DataFrame({
        'feature': like_feature_names,
        'importance': like_importance_scores
    }).sort_values('importance', ascending=False)
    
    print(f"\n📊 LIKE FEATURE IMPORTANCE:")
    for idx, row in like_importance_df.iterrows():
        print(f"  {row['feature']:.<25} {row['importance']:.4f}")
    
    # Store feature names for future use
    like_model.feature_names_ = like_feature_names
    like_model.feature_importance_df_ = like_importance_df
    
    return like_model

# ──────────────────────────────────────────────
# 📊 TRAINING SUMMARY
# ──────────────────────────────────────────────
def print_training_summary(rating_models, like_model, rating_records, like_records):
    """Print comprehensive training summary"""
    
    print("\n" + "="*80)
    print("🎯 XGBOOST MODEL TRAINING SUMMARY")
    print("="*80)
    
    # Dataset statistics
    print(f"\n📊 DATASET STATISTICS:")
    print(f"   • Rating records: {len(rating_records):,}")
    print(f"   • Like records: {len(like_records):,}")
    like_count = len([r for r in like_records if r['is_liked']])
    dislike_count = len([r for r in like_records if not r['is_liked']])
    print(f"   • Like/Dislike ratio: {like_count:,}/{dislike_count:,}")
    
    # Rating model insights
    if 'performance' in rating_models:
        perf = rating_models['performance']
        print(f"\n🎯 RATING PREDICTION MODEL:")
        print(f"   • RMSE: {perf['rmse']:.3f}")
        print(f"   • Prediction spread: {perf['pred_std']:.3f} (target: {perf['train_std']:.3f})")
        print(f"   • Spread ratio: {perf['pred_std'] / perf['train_std']:.2f}")
        
        # Top features
        top_features = rating_models['feature_importance'].head(3)
        print(f"   • Top features:")
        for _, row in top_features.iterrows():
            print(f"     - {row['feature']}: {row['importance']:.3f}")
    
    # Like model insights
    if like_model and hasattr(like_model, 'feature_importance_df_'):
        print(f"\n❤️  LIKE PREDICTION MODEL:")
        print(f"   • Accuracy: {accuracy_score}")
        top_like_features = like_model.feature_importance_df_.head(3)
        print(f"   • Top features:")
        for _, row in top_like_features.iterrows():
            print(f"     - {row['feature']}: {row['importance']:.3f}")
    
    # Key findings
    print(f"\n🔍 KEY FINDINGS:")
    if 'performance' in rating_models:
        spread_ratio = rating_models['performance']['pred_std'] / rating_models['performance']['train_std']
        if spread_ratio > 0.8:
            print(f"   ✅ Good prediction spread achieved ({spread_ratio:.2f})")
        else:
            print(f"   ⚠️  Predictions still somewhat centralized ({spread_ratio:.2f})")
    
    if like_model:
        print(f"   ✅ Like prediction model trained successfully")
    else:
        print(f"   ⚠️  Using fallback for like predictions")
    
    print("="*80)

# ──────────────────────────────────────────────
# 💾 SAVE MODELS
# ──────────────────────────────────────────────
def save_xgboost_models(rating_models, like_model, models_collection):
    """Save XGBoost models to MongoDB with proper type conversion"""
    model_data = {
        "name": "predictor",
        "last_updated": datetime.utcnow(),
        "model_type": "xgboost",
        "feature_columns": rating_models['feature_columns'],
        "rating_performance": {
            'rmse': float(rating_models['performance']['rmse']),
            'mse': float(rating_models['performance']['mse']),
            'pred_mean': float(rating_models['performance']['pred_mean']),
            'pred_std': float(rating_models['performance']['pred_std']),
            'train_std': float(rating_models['performance']['train_std'])
        }
    }
    
    # Save rating model
    rating_model_bytes = pickle.dumps(rating_models['model'])
    model_data["rating_model_b64"] = base64.b64encode(rating_model_bytes).decode("utf-8")
    
    # Save feature importance with proper type conversion
    rating_importance_list = []
    for _, row in rating_models['feature_importance'].iterrows():
        rating_importance_list.append({
            'feature': row['feature'],
            'importance': float(row['importance'])  # Convert numpy float to Python float
        })
    model_data["rating_feature_importance"] = rating_importance_list
    
    # Save like model if available
    if like_model:
        like_model_bytes = pickle.dumps(like_model)
        model_data["like_model_b64"] = base64.b64encode(like_model_bytes).decode("utf-8")
        
        # Convert like feature importance
        like_importance_list = []
        for _, row in like_model.feature_importance_df_.iterrows():
            like_importance_list.append({
                'feature': row['feature'],
                'importance': float(row['importance'])  # Convert numpy float to Python float
            })
        model_data["like_feature_importance"] = like_importance_list
        model_data["has_like_model"] = True
    else:
        model_data["has_like_model"] = False
        model_data["like_feature_importance"] = []
        logging.info("Using fallback like prediction (threshold-based)")
    
    # Convert all numpy values in the model_data recursively
    model_data = convert_numpy_types(model_data)
    
    models_collection.replace_one(
        {"name": "predictor"},
        model_data,
        upsert=True
    )
    
    logging.info("Models saved to MongoDB successfully")

def convert_numpy_types(obj):
    """Recursively convert numpy types to native Python types for MongoDB serialization"""
    if isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, (np.float32, np.float64)):
        return float(obj)
    elif isinstance(obj, (np.int32, np.int64)):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj

# ──────────────────────────────────────────────
# 🚀 MAIN TRAINING PIPELINE
# ──────────────────────────────────────────────
def main():
    logging.info("Starting XGBoost model training pipeline...")
    
    try:
        # Extract data
        rating_records, like_records, users_data = extract_enhanced_training_data()
        logging.info(f"Extracted {len(rating_records)} rating records and {len(like_records)} like records")
        
        if not rating_records:
            logging.error("No rating records found. Exiting.")
            return
        
        # Train XGBoost rating model
        rating_models = train_xgboost_rating_model(rating_records)
        
        # Train XGBoost like model
        like_model = train_xgboost_like_model(like_records, rating_models, users_data)
        
        # Print comprehensive summary
        print_training_summary(rating_models, like_model, rating_records, like_records)
        
        # Save models
        models_col = db[MODELS_COLLECTION]
        save_xgboost_models(rating_models, like_model, models_col)
        
        logging.info("✅ XGBoost model training completed successfully!")
        
    except Exception as e:
        logging.error(f"❌ Training failed: {e}")
        raise

if __name__ == "__main__":
    main()