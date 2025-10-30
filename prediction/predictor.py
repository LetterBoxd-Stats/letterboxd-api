"""
Enhanced predictor.py for XGBoost models
"""

import pickle
import base64
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import numpy as np
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB configuration
DB_URI = os.getenv("DB_URI")
DB_NAME = os.getenv("DB_NAME")
MODELS_COLLECTION = os.getenv("DB_MODELS_COLLECTION")
USERS_COLLECTION = os.getenv("DB_USERS_COLLECTION")
FILMS_COLLECTION = os.getenv("DB_FILMS_COLLECTION")

# Cache for loaded model
_model_cache = None

def get_model():
    """Load both rating and like models from MongoDB"""
    global _model_cache
    
    if _model_cache is None:
        client = MongoClient(DB_URI)
        db = client[DB_NAME]
        models_col = db[MODELS_COLLECTION]
        
        # Try both model names for backward compatibility
        model_doc = models_col.find_one({"name": "predictor"})
        if not model_doc:
            model_doc = models_col.find_one({"name": "predictor"})
            if not model_doc:
                raise RuntimeError("No trained model found in MongoDB.")
        
        # Load rating model
        rating_model_bytes = base64.b64decode(model_doc["rating_model_b64"])
        rating_model = pickle.loads(rating_model_bytes)
        
        # Load like model if available
        like_model = None
        if model_doc.get("has_like_model", False) and "like_model_b64" in model_doc:
            like_model_bytes = base64.b64decode(model_doc["like_model_b64"])
            like_model = pickle.loads(like_model_bytes)
        
        # Get feature columns and model info
        feature_columns = model_doc.get("feature_columns", [])
        model_type = model_doc.get("model_type", "unknown")
        
        _model_cache = {
            "rating_model": rating_model,
            "like_model": like_model,
            "has_like_model": model_doc.get("has_like_model", False),
            "feature_columns": feature_columns,
            "model_type": model_type
        }
        
        logger.info(f"Loaded {model_type} model with {len(feature_columns)} features")
    
    return _model_cache

def predict_rating(model_dict, username, film_id, film_data):
    """Predict rating using XGBoost model with proper feature engineering"""
    try:
        # Get user stats
        user_stats = get_user_stats(username)
        
        # Get film stats
        film_stats = get_film_stats(film_data)
        
        # Create feature vector
        features = create_rating_feature_vector(user_stats, film_stats, model_dict["feature_columns"])
        
        # Convert to DataFrame with proper column names
        feature_df = pd.DataFrame([features], columns=model_dict["feature_columns"])
        
        # Predict rating
        predicted_rating = model_dict["rating_model"].predict(feature_df)[0]
        
        # Clip to valid rating range
        predicted_rating = max(0.5, min(5.0, float(predicted_rating)))
        
        return round(predicted_rating, 2)
        
    except Exception as e:
        logger.error(f"Rating prediction failed for {username}, {film_id}: {e}")
        return None

def create_rating_feature_vector(user_stats, film_stats, feature_columns):
    """Create feature vector matching training features for RATING prediction"""
    # Default values for all possible features
    feature_defaults = {
        'user_avg_rating': 3.0,
        'user_stdev_rating': 1.0,
        'film_avg_rating': 3.0,
        'film_num_ratings': 1,
        'film_letterboxd_avg': 3.0,
        'film_runtime': 120,
        'film_year': 2000,
        'max_genre_rating': 3.0,
        'min_genre_rating': 3.0,
        'avg_genre_rating': 3.0,
        'total_genre_watches': 0
    }
    
    # Update with actual values
    feature_defaults.update(user_stats)
    feature_defaults.update(film_stats)
    
    # Create feature vector in correct order
    feature_vector = [feature_defaults.get(col, 0.0) for col in feature_columns]
    
    return feature_vector

def get_user_stats(username):
    """Get comprehensive user statistics for feature engineering"""
    try:
        client = MongoClient(DB_URI)
        db = client[DB_NAME]
        users_collection = db[USERS_COLLECTION]
        
        user_doc = users_collection.find_one(
            {"username": username}, 
            {"_id": 0, "stats": 1}
        )
        
        if not user_doc or "stats" not in user_doc:
            return get_default_user_stats()
        
        stats = user_doc["stats"]
        
        # Calculate genre compatibility stats
        genre_stats = calculate_user_genre_stats(stats)
        
        user_data = {
            'user_avg_rating': stats.get("avg_rating", 3.0),
            'user_stdev_rating': stats.get("stdev_rating", 1.0),
            'user_like_ratio': stats.get("like_ratio", 0.5),
            'user_num_ratings': stats.get("num_ratings", 1),
            'user_num_likes': stats.get("num_likes", 0),
            'user_rating_consistency': stats.get("mean_abs_diff", 0.5),
            **genre_stats
        }
        
        return user_data
        
    except Exception as e:
        logger.warning(f"Error getting stats for user {username}: {e}")
        return get_default_user_stats()
    finally:
        client.close()

def get_film_stats(film_data, username=None):
    """Extract film statistics for feature engineering, handling films with no reviews"""
    try:
        metadata = film_data.get("metadata", {})
        genres = metadata.get("genres", [])
        
        # Handle films with no reviews (only watches)
        film_avg_rating = film_data.get("avg_rating")
        if film_avg_rating is None:
            # Use Letterboxd average as fallback for films with no reviews
            film_avg_rating = metadata.get("avg_rating", 3.0)
        
        film_stats = {
            'film_avg_rating': film_avg_rating,  # Now guaranteed to have a value
            'film_like_ratio': film_data.get("like_ratio", 0.5),
            'film_num_ratings': film_data.get("num_ratings", 0),  # Could be 0 for watches-only
            'film_num_watches': film_data.get("num_watches", 0),
            'film_letterboxd_avg': metadata.get("avg_rating", 3.0),
            'film_runtime': metadata.get("runtime", 120),
            'film_year': metadata.get("year", 2000),
            'film_genres': genres,
            'film_has_reviews': film_data.get("num_ratings", 0) > 0  # Flag for films with reviews
        }
        
        return film_stats
        
    except Exception as e:
        logger.warning(f"Error getting film stats: {e}")
        return get_default_film_stats()

def predict_rating(model_dict, username, film_id, film_data):
    """Predict rating using XGBoost model - handle films with no reviews"""
    try:
        # Get user stats
        user_stats = get_user_stats(username)
        
        # Get film stats (this now handles films with no reviews)
        film_stats = get_film_stats(film_data)
        
        # For films with no reviews, we might want to adjust our confidence
        if not film_stats.get('film_has_reviews', True):
            logger.info(f"Predicting rating for film {film_id} with no review history")
        
        # Create feature vector
        features = create_rating_feature_vector(user_stats, film_stats, model_dict["feature_columns"])
        
        # Convert to DataFrame with proper column names
        feature_df = pd.DataFrame([features], columns=model_dict["feature_columns"])
        
        # Predict rating
        predicted_rating = model_dict["rating_model"].predict(feature_df)[0]
        
        # Clip to valid rating range
        predicted_rating = max(0.5, min(5.0, float(predicted_rating)))
        
        return round(predicted_rating, 2)
        
    except Exception as e:
        logger.error(f"Rating prediction failed for {username}, {film_id}: {e}")
        return None

def predict_like(model_dict, username, film_id, film_data, predicted_rating):
    """Predict whether a user will like a film - handle films with no reviews"""
    
    # If no like model is available, fall back to threshold-based approach
    if not model_dict.get("has_like_model") or model_dict["like_model"] is None:
        logger.info("Using fallback like prediction")
        return predicted_rating >= 3.5 if predicted_rating is not None else None
    
    try:
        # Get user and film stats (pass username to exclude user from film like ratio)
        user_stats = get_user_stats(username)
        film_stats = get_film_stats(film_data, username)
        
        # Get the actual feature names from the trained model
        if hasattr(model_dict["like_model"], 'feature_names_'):
            like_feature_names = model_dict["like_model"].feature_names_
        else:
            # Fallback to our expected feature names
            like_feature_names = [
                'user_like_ratio',
                'user_rating_consistency',
                'film_avg_rating', 
                'film_like_ratio',
                'film_num_ratings',
                'film_letterboxd_avg',
                'film_runtime',
                'film_year',
                'avg_genre_like_ratio',
                'total_genre_watches'
            ]
        
        # Prepare features for like prediction
        features = []
        for feature_name in like_feature_names:
            if feature_name == 'user_like_ratio':
                features.append(user_stats['user_like_ratio'])
            elif feature_name == 'user_rating_consistency':
                features.append(user_stats['user_rating_consistency'])
            elif feature_name == 'film_avg_rating':
                features.append(film_stats['film_avg_rating'])  # Now always has a value
            elif feature_name == 'film_like_ratio':
                features.append(film_stats['film_like_ratio'])
            elif feature_name == 'film_num_ratings':
                features.append(film_stats['film_num_ratings'])
            elif feature_name == 'film_letterboxd_avg':
                features.append(film_stats['film_letterboxd_avg'])
            elif feature_name == 'film_runtime':
                features.append(film_stats['film_runtime'])
            elif feature_name == 'film_year':
                features.append(film_stats['film_year'])
            elif feature_name == 'avg_genre_like_ratio':
                features.append(user_stats['avg_genre_like_ratio'])
            elif feature_name == 'total_genre_watches':
                features.append(user_stats['total_genre_watches'])
            else:
                # Default value for unknown features
                logger.warning(f"Unknown feature in like model: {feature_name}")
                features.append(0.0)
        
        # Convert to numpy array and DataFrame
        features_array = np.array([features])
        feature_df = pd.DataFrame(features_array, columns=like_feature_names)
        
        # Predict like probability
        like_prob = model_dict["like_model"].predict_proba(feature_df)[0][1]
        
        logger.debug(f"Like probability for {username}: {like_prob:.3f}")
        logger.debug(f"Film has reviews: {film_stats.get('film_has_reviews', 'unknown')}")
        
        # Return True if probability > 0.5
        return like_prob > 0.5
        
    except Exception as e:
        logger.warning(f"Like prediction failed for {username}, {film_id}: {e}")
        # Fallback to threshold-based approach
        return predicted_rating >= 3.5 if predicted_rating is not None else None
        
    except Exception as e:
        logger.warning(f"Error getting film stats: {e}")
        return get_default_film_stats()

def calculate_user_genre_stats(user_stats):
    """Calculate genre compatibility statistics"""
    genre_stats_data = user_stats.get("genre_stats", {})
    
    if not genre_stats_data:
        return {
            'max_genre_rating': 3.0,
            'min_genre_rating': 3.0,
            'avg_genre_rating': 3.0,
            'total_genre_watches': 0,
            'avg_genre_like_ratio': user_stats.get("like_ratio", 0.5)
        }
    
    genre_ratings = []
    genre_like_ratios = []
    genre_counts = []
    
    for genre, stats in genre_stats_data.items():
        if stats.get("avg_rating") is not None:
            genre_ratings.append(stats["avg_rating"])
            genre_counts.append(stats.get("count", 0))
        if stats.get("like_ratio") is not None:
            genre_like_ratios.append(stats["like_ratio"])
    
    if genre_ratings:
        rating_stats = {
            'max_genre_rating': max(genre_ratings),
            'min_genre_rating': min(genre_ratings),
            'avg_genre_rating': sum(genre_ratings) / len(genre_ratings),
            'total_genre_watches': sum(genre_counts)
        }
    else:
        rating_stats = {
            'max_genre_rating': user_stats.get("avg_rating", 3.0),
            'min_genre_rating': user_stats.get("avg_rating", 3.0),
            'avg_genre_rating': user_stats.get("avg_rating", 3.0),
            'total_genre_watches': 0
        }
    
    # Add like ratio stats
    if genre_like_ratios:
        rating_stats['avg_genre_like_ratio'] = sum(genre_like_ratios) / len(genre_like_ratios)
    else:
        rating_stats['avg_genre_like_ratio'] = user_stats.get("like_ratio", 0.5)
    
    return rating_stats

def predict_like(model_dict, username, film_id, film_data, predicted_rating):
    """Predict whether a user will like a film using the trained like model"""
    
    # If no like model is available, fall back to threshold-based approach
    if not model_dict.get("has_like_model") or model_dict["like_model"] is None:
        logger.info("Using fallback like prediction")
        return predicted_rating >= 3.5 if predicted_rating is not None else None
    
    try:
        # Get user and film stats
        user_stats = get_user_stats(username)
        film_stats = get_film_stats(film_data)
        
        # Get the actual feature names from the trained model
        if hasattr(model_dict["like_model"], 'feature_names_'):
            like_feature_names = model_dict["like_model"].feature_names_
        else:
            # Fallback to our expected feature names
            like_feature_names = [
                'user_like_ratio',
                'user_rating_consistency',
                'film_avg_rating', 
                'film_like_ratio',  # This might be the missing feature
                'film_num_ratings',
                'film_letterboxd_avg',
                'film_runtime',
                'film_year',
                'avg_genre_like_ratio',
                'total_genre_watches'
            ]
        
        # Prepare features for like prediction
        features = []
        for feature_name in like_feature_names:
            if feature_name == 'user_like_ratio':
                features.append(user_stats['user_like_ratio'])
            elif feature_name == 'user_rating_consistency':
                features.append(user_stats['user_rating_consistency'])
            elif feature_name == 'film_avg_rating':
                features.append(film_stats['film_avg_rating'])
            elif feature_name == 'film_like_ratio':
                features.append(film_stats['film_like_ratio'])  # This might be causing leakage
            elif feature_name == 'film_num_ratings':
                features.append(film_stats['film_num_ratings'])
            elif feature_name == 'film_letterboxd_avg':
                features.append(film_stats['film_letterboxd_avg'])
            elif feature_name == 'film_runtime':
                features.append(film_stats['film_runtime'])
            elif feature_name == 'film_year':
                features.append(film_stats['film_year'])
            elif feature_name == 'avg_genre_like_ratio':
                features.append(user_stats['avg_genre_like_ratio'])
            elif feature_name == 'total_genre_watches':
                features.append(user_stats['total_genre_watches'])
            else:
                # Default value for unknown features
                logger.warning(f"Unknown feature in like model: {feature_name}")
                features.append(0.0)
        
        # Convert to numpy array and DataFrame
        features_array = np.array([features])
        feature_df = pd.DataFrame(features_array, columns=like_feature_names)
        
        # Predict like probability
        like_prob = model_dict["like_model"].predict_proba(feature_df)[0][1]
        
        logger.debug(f"Like probability for {username}: {like_prob:.3f}")
        logger.debug(f"Used {len(like_feature_names)} features: {like_feature_names}")
        
        # Return True if probability > 0.5
        return like_prob > 0.5
        
    except Exception as e:
        logger.warning(f"Like prediction failed for {username}, {film_id}: {e}")
        # Fallback to threshold-based approach
        return predicted_rating >= 3.5 if predicted_rating is not None else None

def get_default_user_stats():
    """Return default user statistics when user data is not available"""
    return {
        'user_avg_rating': 3.0,
        'user_stdev_rating': 1.0,
        'user_like_ratio': 0.5,
        'user_num_ratings': 1,
        'user_num_likes': 0,
        'user_rating_consistency': 0.5,
        'max_genre_rating': 3.0,
        'min_genre_rating': 3.0,
        'avg_genre_rating': 3.0,
        'total_genre_watches': 0,
        'avg_genre_like_ratio': 0.5
    }

def get_default_film_stats():
    """Return default film statistics when film data is not available"""
    return {
        'film_avg_rating': 3.0,
        'film_like_ratio': 0.5,
        'film_num_ratings': 0,  # Could be 0 for watches-only films
        'film_num_watches': 1,
        'film_letterboxd_avg': 3.0,
        'film_runtime': 120,
        'film_year': 2000,
        'film_genres': [],
        'film_has_reviews': False
    }