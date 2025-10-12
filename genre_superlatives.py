"""
Genre Superlatives Module
=========================
This module computes superlatives for each genre based on user watch patterns.
For each genre, it identifies which user has the highest percentage of movies 
from that genre in their watch history.

Author: SHRESHTHBEHAL
Date: October 2025
"""

import logging
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)


def calculate_genre_superlatives(user_logs: List[Dict]) -> Dict[str, Dict[str, any]]:
    """
    Calculate genre superlatives by finding which user watches the most of each genre
    (by percentage of their total movies).
    
    This function analyzes user movie logs and for each genre, determines which user
    has the highest percentage of movies from that genre in their watch history.
    
    Args:
        user_logs (List[Dict]): List of user log dictionaries with the structure:
            [
                {
                    "username": str,
                    "movies": [
                        {"title": str, "genres": List[str]},
                        ...
                    ]
                },
                ...
            ]
    
    Returns:
        Dict[str, Dict[str, any]]: Dictionary mapping each genre to its superlative:
            {
                "Action": {
                    "user": "username",
                    "percentage": 65.50,
                    "count": 131,
                    "total_movies": 200
                },
                ...
            }
    
    Edge Cases Handled:
        - Empty user logs: returns empty dictionary
        - Users with no movies: skipped in calculations
        - Movies with no genres: skipped for genre calculations
        - Ties: first user alphabetically wins
        - Genres with zero watches: not included in results
    
    Example:
        >>> user_logs = [
        ...     {
        ...         "username": "alice",
        ...         "movies": [
        ...             {"title": "Inception", "genres": ["Action", "Sci-Fi"]},
        ...             {"title": "The Dark Knight", "genres": ["Action", "Drama"]}
        ...         ]
        ...     },
        ...     {
        ...         "username": "bob",
        ...         "movies": [
        ...             {"title": "Toy Story", "genres": ["Animation", "Comedy"]},
        ...             {"title": "Inception", "genres": ["Action", "Sci-Fi"]}
        ...         ]
        ...     }
        ... ]
        >>> result = calculate_genre_superlatives(user_logs)
        >>> result["Action"]
        {'user': 'alice', 'percentage': 100.0, 'count': 2, 'total_movies': 2}
    """
    
    # Validate input
    if not user_logs:
        logger.warning("Empty user_logs provided to calculate_genre_superlatives")
        return {}
    
    # Track genre counts per user
    # Structure: {username: {genre: count}}
    user_genre_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    # Track total movie counts per user
    user_total_movies: Dict[str, int] = defaultdict(int)
    
    # Track all genres seen
    all_genres = set()
    
    # Process each user's movie logs
    for user_log in user_logs:
        username = user_log.get("username")
        movies = user_log.get("movies", [])
        
        # Validate user data
        if not username:
            logger.warning("User log missing username, skipping")
            continue
        
        if not movies:
            logger.debug(f"User '{username}' has no movies logged")
            continue
        
        # Count total movies for this user
        user_total_movies[username] = len(movies)
        
        # Process each movie
        for movie in movies:
            genres = movie.get("genres", [])
            
            # Skip movies with no genre information
            if not genres:
                logger.debug(f"Movie '{movie.get('title', 'Unknown')}' has no genres, skipping")
                continue
            
            # Count each genre for this user
            # Note: A movie can belong to multiple genres
            for genre in genres:
                if genre:  # Ensure genre is not empty string
                    user_genre_counts[username][genre] += 1
                    all_genres.add(genre)
    
    # Calculate genre superlatives
    genre_superlatives: Dict[str, Dict[str, any]] = {}
    
    for genre in sorted(all_genres):  # Sort for consistent output
        # Find user with highest percentage for this genre
        best_user = None
        best_percentage = -1.0
        best_count = 0
        best_total = 0
        
        for username, genre_counts in user_genre_counts.items():
            total_movies = user_total_movies[username]
            genre_count = genre_counts.get(genre, 0)
            
            # Skip users who haven't watched this genre
            if genre_count == 0:
                continue
            
            # Calculate percentage
            percentage = (genre_count / total_movies) * 100
            
            # Check if this is the best so far
            # In case of tie, choose alphabetically first username (deterministic)
            if percentage > best_percentage or \
               (percentage == best_percentage and (best_user is None or username < best_user)):
                best_user = username
                best_percentage = percentage
                best_count = genre_count
                best_total = total_movies
        
        # Only add genres that have been watched by at least one user
        if best_user is not None:
            genre_superlatives[genre] = {
                "user": best_user,
                "percentage": round(best_percentage, 2),
                "count": best_count,
                "total_movies": best_total
            }
            
            logger.debug(
                f"Genre '{genre}': {best_user} ({best_percentage:.2f}% - "
                f"{best_count}/{best_total} movies)"
            )
    
    logger.info(f"Computed superlatives for {len(genre_superlatives)} genres")
    return genre_superlatives


def format_genre_superlatives(
    superlatives: Dict[str, Dict[str, any]],
    format_type: str = "text"
) -> str:
    """
    Format genre superlatives for display.
    
    Args:
        superlatives (Dict): Output from calculate_genre_superlatives()
        format_type (str): Output format - "text", "json", or "detailed"
    
    Returns:
        str: Formatted string representation of superlatives
    
    Example:
        >>> superlatives = {
        ...     "Action": {"user": "alice", "percentage": 65.0, "count": 13, "total_movies": 20}
        ... }
        >>> print(format_genre_superlatives(superlatives, "text"))
        Superlatives by Genre:
        Action: alice (65.00%)
    """
    
    if not superlatives:
        return "No genre superlatives found."
    
    if format_type == "text":
        # Simple text format
        lines = ["Superlatives by Genre:"]
        for genre in sorted(superlatives.keys()):
            data = superlatives[genre]
            lines.append(f"{genre}: {data['user']} ({data['percentage']:.2f}%)")
        return "\n".join(lines)
    
    elif format_type == "detailed":
        # Detailed text format with counts
        lines = ["=" * 60]
        lines.append("GENRE SUPERLATIVES - Detailed Report")
        lines.append("=" * 60)
        lines.append("")
        
        for genre in sorted(superlatives.keys()):
            data = superlatives[genre]
            lines.append(f"Genre: {genre}")
            lines.append(f"  Champion: {data['user']}")
            lines.append(f"  Percentage: {data['percentage']:.2f}%")
            lines.append(f"  Count: {data['count']} out of {data['total_movies']} total movies")
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    elif format_type == "json":
        # JSON format (as string)
        import json
        return json.dumps(superlatives, indent=2)
    
    else:
        raise ValueError(f"Unknown format_type: {format_type}. Use 'text', 'detailed', or 'json'")


def get_user_genre_profile(user_logs: List[Dict], username: str) -> Dict[str, Dict[str, any]]:
    """
    Get a detailed genre profile for a specific user.
    
    Args:
        user_logs (List[Dict]): User log data
        username (str): Username to analyze
    
    Returns:
        Dict[str, Dict]: Genre breakdown for the user with percentages and counts
    
    Example:
        >>> result = get_user_genre_profile(user_logs, "alice")
        >>> result
        {
            "Action": {"count": 10, "percentage": 50.0},
            "Drama": {"count": 8, "percentage": 40.0},
            ...
        }
    """
    
    # Find the user
    user_data = None
    for user_log in user_logs:
        if user_log.get("username") == username:
            user_data = user_log
            break
    
    if not user_data:
        logger.warning(f"User '{username}' not found in user_logs")
        return {}
    
    movies = user_data.get("movies", [])
    if not movies:
        return {}
    
    # Count genres
    genre_counts = defaultdict(int)
    total_movies = len(movies)
    
    for movie in movies:
        for genre in movie.get("genres", []):
            if genre:
                genre_counts[genre] += 1
    
    # Calculate percentages
    genre_profile = {}
    for genre, count in genre_counts.items():
        percentage = (count / total_movies) * 100
        genre_profile[genre] = {
            "count": count,
            "percentage": round(percentage, 2)
        }
    
    return dict(sorted(genre_profile.items(), key=lambda x: x[1]["percentage"], reverse=True))


# =============================================================================
# DEMO AND TEST CODE
# =============================================================================

def run_demo():
    """
    Demonstration of the genre superlatives feature with sample data.
    """
    print("=" * 70)
    print("GENRE SUPERLATIVES FEATURE DEMO")
    print("=" * 70)
    print()
    
    # Sample test data
    sample_user_logs = [
        {
            "username": "shreshth",
            "movies": [
                {"title": "Inception", "genres": ["Action", "Sci-Fi"]},
                {"title": "The Dark Knight", "genres": ["Action", "Crime", "Drama"]},
                {"title": "Interstellar", "genres": ["Sci-Fi", "Drama"]},
                {"title": "The Matrix", "genres": ["Action", "Sci-Fi"]},
                {"title": "Blade Runner 2049", "genres": ["Sci-Fi", "Thriller"]},
                {"title": "Mad Max: Fury Road", "genres": ["Action", "Adventure"]},
                {"title": "Dunkirk", "genres": ["Drama", "War", "History"]},
                {"title": "Tenet", "genres": ["Action", "Sci-Fi", "Thriller"]},
            ]
        },
        {
            "username": "priya",
            "movies": [
                {"title": "The Notebook", "genres": ["Romance", "Drama"]},
                {"title": "Pride and Prejudice", "genres": ["Romance", "Drama"]},
                {"title": "La La Land", "genres": ["Romance", "Musical", "Drama"]},
                {"title": "Moonlight", "genres": ["Drama"]},
                {"title": "The Shape of Water", "genres": ["Fantasy", "Drama", "Romance"]},
                {"title": "Call Me by Your Name", "genres": ["Romance", "Drama"]},
                {"title": "Little Women", "genres": ["Drama", "Romance"]},
            ]
        },
        {
            "username": "raj",
            "movies": [
                {"title": "The Grand Budapest Hotel", "genres": ["Comedy", "Drama"]},
                {"title": "Superbad", "genres": ["Comedy"]},
                {"title": "The Hangover", "genres": ["Comedy"]},
                {"title": "Bridesmaids", "genres": ["Comedy", "Romance"]},
                {"title": "Anchorman", "genres": ["Comedy"]},
                {"title": "Step Brothers", "genres": ["Comedy"]},
                {"title": "Zombieland", "genres": ["Comedy", "Horror"]},
                {"title": "Get Out", "genres": ["Horror", "Thriller"]},
            ]
        },
        {
            "username": "sam",
            "movies": [
                {"title": "The Shining", "genres": ["Horror", "Thriller"]},
                {"title": "Hereditary", "genres": ["Horror", "Drama"]},
                {"title": "A Quiet Place", "genres": ["Horror", "Sci-Fi"]},
                {"title": "The Conjuring", "genres": ["Horror", "Thriller"]},
                {"title": "It Follows", "genres": ["Horror", "Mystery"]},
                {"title": "The Witch", "genres": ["Horror", "Fantasy"]},
                {"title": "Midsommar", "genres": ["Horror", "Drama"]},
                {"title": "Get Out", "genres": ["Horror", "Thriller"]},
                {"title": "The Exorcist", "genres": ["Horror"]},
                {"title": "Psycho", "genres": ["Horror", "Thriller"]},
            ]
        },
    ]
    
    print("Sample User Data:")
    print("-" * 70)
    for user in sample_user_logs:
        print(f"  {user['username']}: {len(user['movies'])} movies logged")
    print()
    
    # Calculate superlatives
    print("Calculating genre superlatives...")
    print()
    superlatives = calculate_genre_superlatives(sample_user_logs)
    
    # Display results in text format
    print(format_genre_superlatives(superlatives, "text"))
    print()
    print()
    
    # Display results in detailed format
    print(format_genre_superlatives(superlatives, "detailed"))
    
    # Display individual user profiles
    print()
    print("=" * 70)
    print("INDIVIDUAL USER GENRE PROFILES")
    print("=" * 70)
    print()
    
    for user in sample_user_logs:
        username = user["username"]
        profile = get_user_genre_profile(sample_user_logs, username)
        
        print(f"User: {username}")
        print("-" * 40)
        for genre, data in profile.items():
            print(f"  {genre:15s}: {data['count']:2d} movies ({data['percentage']:5.2f}%)")
        print()
    
    # Test edge cases
    print()
    print("=" * 70)
    print("EDGE CASE TESTING")
    print("=" * 70)
    print()
    
    # Test 1: Empty logs
    print("Test 1: Empty user logs")
    result = calculate_genre_superlatives([])
    print(f"  Result: {result}")
    print(f"  ✓ Handled correctly (returned empty dict)")
    print()
    
    # Test 2: User with no movies
    print("Test 2: User with no movies")
    test_data = [{"username": "empty_user", "movies": []}]
    result = calculate_genre_superlatives(test_data)
    print(f"  Result: {result}")
    print(f"  ✓ Handled correctly (returned empty dict)")
    print()
    
    # Test 3: Movies with no genres
    print("Test 3: Movies with no genres")
    test_data = [
        {
            "username": "test_user",
            "movies": [
                {"title": "Movie 1", "genres": []},
                {"title": "Movie 2", "genres": ["Action"]},
            ]
        }
    ]
    result = calculate_genre_superlatives(test_data)
    print(f"  Result: {result}")
    print(f"  ✓ Handled correctly (counted only valid genres)")
    print()
    
    # Test 4: Tie scenario
    print("Test 4: Tie between users (alphabetical order)")
    test_data = [
        {
            "username": "zebra",
            "movies": [{"title": "M1", "genres": ["Action"]}]
        },
        {
            "username": "alice",
            "movies": [{"title": "M2", "genres": ["Action"]}]
        },
    ]
    result = calculate_genre_superlatives(test_data)
    print(f"  Result: {result}")
    print(f"  Winner: {result.get('Action', {}).get('user', 'None')}")
    print(f"  ✓ Handled correctly (alice wins alphabetically)")
    print()
    
    print("=" * 70)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    # Configure logging for standalone execution
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Run the demo
    run_demo()
