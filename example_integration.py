"""
Example Integration Script
===========================
This script demonstrates how the genre superlatives feature integrates with
the existing LetterBoxd API database structure.

This is a demonstration only - the actual integration is done in stats.py.
"""

import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def convert_db_format_to_user_logs(users_from_db: List[Dict]) -> List[Dict]:
    """
    Convert users from database format to the format expected by genre_superlatives.
    
    Database format (from MongoDB):
        {
            "username": "shreshth",
            "reviews": [
                {"film_id": "123", "film_title": "Inception", ...},
                ...
            ],
            "watches": [
                {"film_id": "456", "film_title": "The Matrix", ...},
                ...
            ]
        }
    
    genre_superlatives expected format:
        {
            "username": "shreshth",
            "movies": [
                {"title": "Inception", "genres": ["Action", "Sci-Fi"]},
                ...
            ]
        }
    
    Args:
        users_from_db: Users in database format
    
    Returns:
        Users in genre_superlatives format
    """
    logger.info("Converting database format to user_logs format...")
    
    # Note: In the actual implementation in stats.py, we don't need this conversion
    # because we directly use the stats.genre_stats data that's already computed.
    # This is just for demonstration purposes.
    
    user_logs = []
    
    for user in users_from_db:
        username = user.get("username")
        
        # Combine reviews and watches
        all_interactions = []
        all_interactions.extend(user.get("reviews", []))
        all_interactions.extend(user.get("watches", []))
        
        # Note: In reality, we'd need to fetch film metadata to get genres
        # But in stats.py, this is already available in the genre_stats
        
        movies = []
        for interaction in all_interactions:
            # In production, you would fetch this from films collection
            # or from the already-computed genre_stats
            movie = {
                "title": interaction.get("film_title", "Unknown"),
                "genres": interaction.get("genres", [])  # Would come from film metadata
            }
            movies.append(movie)
        
        user_logs.append({
            "username": username,
            "movies": movies
        })
    
    logger.info(f"Converted {len(user_logs)} users")
    return user_logs


def demonstrate_integration():
    """
    Demonstrate how the feature integrates with the existing system.
    """
    print("=" * 70)
    print("GENRE SUPERLATIVES INTEGRATION DEMONSTRATION")
    print("=" * 70)
    print()
    
    # Simulate user data as it comes from MongoDB
    print("1. FETCHING USERS FROM DATABASE")
    print("-" * 70)
    
    simulated_db_users = [
        {
            "username": "shreshth",
            "stats": {
                "num_watches": 8,
                "genre_stats": {
                    "Action": {"count": 5, "percentage": 62.50, "avg_rating": 4.2},
                    "Sci-Fi": {"count": 5, "percentage": 62.50, "avg_rating": 4.5},
                    "Drama": {"count": 3, "percentage": 37.50, "avg_rating": 4.0},
                    "Thriller": {"count": 2, "percentage": 25.00, "avg_rating": 3.8},
                }
            }
        },
        {
            "username": "priya",
            "stats": {
                "num_watches": 7,
                "genre_stats": {
                    "Drama": {"count": 7, "percentage": 100.00, "avg_rating": 4.3},
                    "Romance": {"count": 6, "percentage": 85.71, "avg_rating": 4.5},
                    "Musical": {"count": 1, "percentage": 14.29, "avg_rating": 4.0},
                }
            }
        },
        {
            "username": "raj",
            "stats": {
                "num_watches": 8,
                "genre_stats": {
                    "Comedy": {"count": 7, "percentage": 87.50, "avg_rating": 3.9},
                    "Horror": {"count": 2, "percentage": 25.00, "avg_rating": 3.5},
                    "Drama": {"count": 1, "percentage": 12.50, "avg_rating": 4.0},
                }
            }
        },
        {
            "username": "sam",
            "stats": {
                "num_watches": 10,
                "genre_stats": {
                    "Horror": {"count": 10, "percentage": 100.00, "avg_rating": 4.1},
                    "Thriller": {"count": 4, "percentage": 40.00, "avg_rating": 4.0},
                    "Drama": {"count": 2, "percentage": 20.00, "avg_rating": 3.8},
                }
            }
        }
    ]
    
    print(f"Found {len(simulated_db_users)} users in database")
    print()
    
    # Extract genre stats (this is what stats.py actually does)
    print("2. EXTRACTING GENRE STATISTICS")
    print("-" * 70)
    
    all_genres = set()
    for user in simulated_db_users:
        genre_stats = user.get("stats", {}).get("genre_stats", {})
        all_genres.update(genre_stats.keys())
    
    print(f"Found {len(all_genres)} unique genres: {sorted(all_genres)}")
    print()
    
    # Calculate genre superlatives (this is the new code in stats.py)
    print("3. CALCULATING GENRE PERCENTAGE SUPERLATIVES")
    print("-" * 70)
    
    genre_superlatives = []
    
    for genre in sorted(all_genres):
        genre_leaders = []
        
        for user in simulated_db_users:
            stats = user.get("stats", {})
            genre_stats = stats.get("genre_stats", {}).get(genre, {})
            percentage = genre_stats.get("percentage", 0)
            count = genre_stats.get("count", 0)
            
            if count > 0:
                genre_leaders.append({
                    "username": user["username"],
                    "percentage": percentage,
                    "count": count
                })
        
        # Sort by percentage
        genre_leaders.sort(key=lambda x: x["percentage"], reverse=True)
        
        # Create superlative entry
        superlative = {
            "name": f"{genre} Aficionado",
            "description": f"User who watches {genre} films most frequently (by percentage of total movies)",
            "first": [genre_leaders[0]["username"]] if len(genre_leaders) > 0 else [],
            "first_value": genre_leaders[0]["percentage"] if len(genre_leaders) > 0 else None,
            "second": [genre_leaders[1]["username"]] if len(genre_leaders) > 1 else [],
            "second_value": genre_leaders[1]["percentage"] if len(genre_leaders) > 1 else None,
            "third": [genre_leaders[2]["username"]] if len(genre_leaders) > 2 else [],
            "third_value": genre_leaders[2]["percentage"] if len(genre_leaders) > 2 else None,
        }
        
        genre_superlatives.append(superlative)
        
        # Print winner
        if genre_leaders:
            winner = genre_leaders[0]
            print(f"  {genre:15s}: {winner['username']:12s} ({winner['percentage']:6.2f}%)")
    
    print()
    
    # Show what gets stored in database
    print("4. STORING IN DATABASE (superlatives collection)")
    print("-" * 70)
    print(f"Computed {len(genre_superlatives)} genre superlatives")
    print()
    print("Sample superlative entry:")
    print("-" * 70)
    
    import json
    print(json.dumps(genre_superlatives[0], indent=2))
    print()
    
    # Show API response
    print("5. API ENDPOINT RESPONSE")
    print("-" * 70)
    print("GET /superlatives")
    print()
    print("Response includes these new entries:")
    print()
    
    for sup in genre_superlatives[:3]:  # Show first 3
        print(f"  • {sup['name']}: {sup['first'][0] if sup['first'] else 'N/A'} "
              f"({sup['first_value']:.2f}%)")
    print(f"  ... and {len(genre_superlatives) - 3} more genre superlatives")
    print()
    
    # Summary
    print("=" * 70)
    print("INTEGRATION SUMMARY")
    print("=" * 70)
    print()
    print("✅ Uses existing genre_stats data from compute_user_stats()")
    print("✅ Integrates seamlessly into compute_superlatives()")
    print("✅ Stored in DB_SUPERLATIVES_COLLECTION alongside other superlatives")
    print("✅ Accessible via GET /superlatives API endpoint")
    print("✅ No additional database queries needed")
    print("✅ Minimal performance impact")
    print()
    print("=" * 70)


def show_before_after():
    """Show what the superlatives collection looks like before and after."""
    print("\n")
    print("=" * 70)
    print("BEFORE AND AFTER COMPARISON")
    print("=" * 70)
    print()
    
    print("BEFORE: Existing superlatives")
    print("-" * 70)
    existing = [
        "Positive Polly",
        "Negative Nelly", 
        "BFFs",
        "Enemies",
        "Best Attention Span",
        "Best Movie",
        "Worst Movie",
        "Action Enthusiast",  # Based on ratings relative to user average
        "Drama Critic",  # Based on ratings relative to user average
    ]
    for name in existing:
        print(f"  • {name}")
    print()
    
    print("AFTER: With new genre percentage superlatives")
    print("-" * 70)
    print("All previous superlatives PLUS:")
    print()
    new_ones = [
        "Action Aficionado",      # Based on watch percentage
        "Comedy Aficionado",      # Based on watch percentage
        "Drama Aficionado",       # Based on watch percentage
        "Horror Aficionado",      # Based on watch percentage
        "Romance Aficionado",     # Based on watch percentage
        "... etc (one per genre)"
    ]
    for name in new_ones:
        print(f"  • {name}")
    print()
    
    print("KEY DIFFERENCE:")
    print("-" * 70)
    print("  'Enthusiast' = rates genre higher than their average rating")
    print("  'Aficionado' = watches genre more frequently (higher % of movies)")
    print()
    print("Both metrics provide valuable insights about user preferences!")
    print("=" * 70)


if __name__ == "__main__":
    demonstrate_integration()
    show_before_after()
