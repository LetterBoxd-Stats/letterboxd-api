"""
Enhanced predictor.py with like prediction
"""

import pickle
import base64
from pymongo import MongoClient
import os
from dotenv import load_dotenv
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# MongoDB configuration
DB_URI = os.getenv("DB_URI")
DB_NAME = os.getenv("DB_NAME")
MODELS_COLLECTION = os.getenv("DB_MODELS_COLLECTION")
USERS_COLLECTION = os.getenv("DB_USERS_COLLECTION")

# Cache for loaded model
_model_cache = None

def get_model():
    """Load both rating and like models from MongoDB"""
    global _model_cache
    
    if _model_cache is None:
        client = MongoClient(DB_URI)
        db = client[DB_NAME]
        models_col = db[MODELS_COLLECTION]
        
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
        
        _model_cache = {
            "rating_model": rating_model,
            "like_model": like_model,
            "has_like_model": model_doc.get("has_like_model", False)
        }
    
    return _model_cache

def predict_like(model, username, film_id, film_data, predicted_rating):
    """Predict whether a user will like a film using the trained like model"""
    
    # If no like model is available, fall back to threshold-based approach
    if not model.get("has_like_model") or model["like_model"] is None:
        return predicted_rating >= 3.5 if predicted_rating is not None else None
    
    try:
        # Extract features for like prediction
        film_avg_rating = film_data.get("avg_rating", 0)
        film_like_ratio = film_data.get("like_ratio", 0)
        
        # In a real implementation, you'd want to cache user stats
        # For now, we'll use a simplified approach
        user_stats = get_user_like_stats(username)  # You'd need to implement this
        
        # Prepare feature vector (must match training features)
        features = np.array([[
            predicted_rating,           # Predicted rating
            predicted_rating,           # Actual rating (same as predicted for new predictions)
            film_avg_rating,           # Film's average rating
            film_like_ratio,           # Film's like ratio
            user_stats.get("like_rate", 0.5),  # User's historical like rate
            user_stats.get("review_count", 1), # User's review count
            abs(predicted_rating - film_avg_rating),  # Rating deviation
            abs(predicted_rating - film_avg_rating),  # Predicted rating deviation (same)
        ]])
        
        # Predict like probability
        like_prob = model["like_model"].predict_proba(features)[0][1]
        
        # Return True if probability > 0.5
        return like_prob > 0.5
        
    except Exception as e:
        logger.warning(f"Like prediction failed for {username}, {film_id}: {e}")
        # Fallback to threshold-based approach
        return predicted_rating >= 3.5 if predicted_rating is not None else None

def get_user_like_stats(username):
    """Get user's historical like statistics from the database"""
    try:
        client = MongoClient(DB_URI)
        db = client[DB_NAME]
        users_collection = db[USERS_COLLECTION]
        # Get user document
        user_doc = users_collection.find_one(
            {"username": username}, 
            {"_id": 0, "stats": 1}
        )
        
        if not user_doc or "stats" not in user_doc:
            # Return default values if user not found
            return {
                "like_rate": 0.5,
                "review_count": 1,
                "total_likes": 0,
                "total_ratings": 1
            }
        
        stats = user_doc["stats"]
        num_ratings = stats.get("num_ratings", 0)
        num_likes = stats.get("num_likes", 0)
        
        # Calculate like rate, avoiding division by zero
        if num_ratings > 0:
            like_rate = num_likes / num_ratings
        else:
            like_rate = 0.5  # Default value
        
        return {
            "like_rate": like_rate,
            "review_count": num_ratings,
            "total_likes": num_likes,
            "total_ratings": num_ratings,
            "avg_rating": stats.get("avg_rating", 3.0),
            "rating_stddev": stats.get("stdev_rating", 1.0)
        }
        
    except Exception as e:
        logger.warning(f"Error getting like stats for user {username}: {e}")
        # Return safe default values
        return {
            "like_rate": 0.5,
            "review_count": 1,
            "total_likes": 0,
            "total_ratings": 1,
            "avg_rating": 3.0,
            "rating_stddev": 1.0
        }
    finally:
        client.close()