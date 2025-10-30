from flask import Blueprint, jsonify
from api.db import get_db
import api.config
import logging
from prediction.predictor import get_model, predict_rating, predict_like
import traceback
import numpy as np

logger = logging.getLogger(__name__)
predict_bp = Blueprint("predict", __name__, url_prefix="/predict")

@predict_bp.route("/<film_id>")
def predict_film(film_id):
    """
    GET /predict/<film_id>
    Returns predicted ratings AND likes for all users for a given film.
    Uses XGBoost models for both rating and like prediction.
    """
    db = get_db()
    users_collection = db[api.config.DB_USERS_COLLECTION]
    films_collection = db[api.config.DB_FILMS_COLLECTION]

    try:
        model_dict = get_model()  # Get the model dictionary with both models
        logger.info(f"Using {model_dict['model_type']} model for predictions")
    except Exception as e:
        logger.error(f"Error loading model: {traceback.format_exc()}")
        return jsonify({"error": "Failed to load prediction model"}), 500

    try:
        users = list(users_collection.find({}, {"_id": 0, "username": 1}))
        film = films_collection.find_one({"film_id": film_id}, {"_id": 0})

        if not film:
            return jsonify({"error": f"Film with id {film_id} not found"}), 404

        predictions = []
        for user in users:
            username = user["username"]

            # Check if user has already rated
            rating_doc = films_collection.find_one(
                {"film_id": film_id, "reviews.user": username},
                {"_id": 0, "reviews.$": 1}
            )
            if rating_doc:
                review = rating_doc["reviews"][0]
                predictions.append({
                    "username": username,
                    "film_id": film_id,
                    "predicted_rating": review["rating"],
                    "predicted_like": review.get("is_liked"),
                    "already_rated": True,
                    "already_watched": True
                })
            else:
                # Check if user has watched but not rated
                watch_doc = films_collection.find_one(
                    {"film_id": film_id, "watches.user": username},
                    {"_id": 0, "watches.$": 1}
                )
                if watch_doc:
                    watch = watch_doc["watches"][0]
                    predictions.append({
                        "username": username,
                        "film_id": film_id,
                        "predicted_rating": None,
                        "predicted_like": watch.get("is_liked"),
                        "already_rated": False,
                        "already_watched": True
                    })
                else:
                    try:
                        # Get predicted rating using XGBoost model
                        predicted_rating = predict_rating(
                            model_dict=model_dict,
                            username=username,
                            film_id=film_id,
                            film_data=film
                        )
                        
                        # Get predicted like
                        predicted_like = predict_like(
                            model_dict=model_dict,
                            username=username,
                            film_id=film_id,
                            film_data=film,
                            predicted_rating=predicted_rating
                        )
                        
                    except Exception as e:
                        logger.warning(f"Prediction failed for user {username}, film {film_id}: {e}")
                        predicted_rating = None
                        predicted_like = None

                    predictions.append({
                        "username": username,
                        "film_id": film_id,
                        "predicted_rating": predicted_rating,
                        "predicted_like": bool(predicted_like) if predicted_like is not None else None,
                        "already_rated": False,
                        "already_watched": False
                    })
        
        return jsonify({
            "film_id": film_id,
            "film_title": film.get("film_title"),
            "total_users": len(predictions),
            "predictions": predictions
        })

    except Exception as e:
        logger.error(f"Error predicting for film {film_id}: {traceback.format_exc()}")
        return jsonify({"error": "Internal server error"}), 500