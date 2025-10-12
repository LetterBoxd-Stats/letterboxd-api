"""
Test Suite for Genre Superlatives Feature
==========================================
This file contains comprehensive tests for the genre superlatives functionality.

Author: SHRESHTHBEHAL
Date: October 2025
"""

import unittest
from genre_superlatives import (
    calculate_genre_superlatives,
    format_genre_superlatives,
    get_user_genre_profile
)


class TestGenreSuperlatives(unittest.TestCase):
    """Test cases for genre superlatives calculation."""
    
    def setUp(self):
        """Set up test data before each test."""
        self.sample_data = [
            {
                "username": "alice",
                "movies": [
                    {"title": "Inception", "genres": ["Action", "Sci-Fi"]},
                    {"title": "The Matrix", "genres": ["Action", "Sci-Fi"]},
                    {"title": "Interstellar", "genres": ["Sci-Fi", "Drama"]},
                    {"title": "The Godfather", "genres": ["Crime", "Drama"]},
                ]
            },
            {
                "username": "bob",
                "movies": [
                    {"title": "The Notebook", "genres": ["Romance", "Drama"]},
                    {"title": "Pride and Prejudice", "genres": ["Romance", "Drama"]},
                ]
            },
            {
                "username": "charlie",
                "movies": [
                    {"title": "The Hangover", "genres": ["Comedy"]},
                    {"title": "Superbad", "genres": ["Comedy"]},
                    {"title": "Anchorman", "genres": ["Comedy"]},
                    {"title": "Step Brothers", "genres": ["Comedy"]},
                ]
            }
        ]
    
    def test_basic_calculation(self):
        """Test basic superlatives calculation."""
        result = calculate_genre_superlatives(self.sample_data)
        
        # Check that we got results
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)
        
        # Check Comedy - charlie should win with 100%
        self.assertIn("Comedy", result)
        self.assertEqual(result["Comedy"]["user"], "charlie")
        self.assertEqual(result["Comedy"]["percentage"], 100.0)
        self.assertEqual(result["Comedy"]["count"], 4)
        
        # Check Sci-Fi - alice should win
        self.assertIn("Sci-Fi", result)
        self.assertEqual(result["Sci-Fi"]["user"], "alice")
        
        # Check Romance - bob should win with 100%
        self.assertIn("Romance", result)
        self.assertEqual(result["Romance"]["user"], "bob")
        self.assertEqual(result["Romance"]["percentage"], 100.0)
    
    def test_empty_logs(self):
        """Test with empty user logs."""
        result = calculate_genre_superlatives([])
        self.assertEqual(result, {})
    
    def test_user_with_no_movies(self):
        """Test with user who has no movies."""
        data = [{"username": "empty_user", "movies": []}]
        result = calculate_genre_superlatives(data)
        self.assertEqual(result, {})
    
    def test_movies_without_genres(self):
        """Test movies that have no genre information."""
        data = [
            {
                "username": "test_user",
                "movies": [
                    {"title": "Movie 1", "genres": []},
                    {"title": "Movie 2", "genres": ["Action"]},
                    {"title": "Movie 3", "genres": ["Action"]},
                ]
            }
        ]
        result = calculate_genre_superlatives(data)
        
        # Should only count the movies with genres
        self.assertIn("Action", result)
        # 2 out of 3 movies = 66.67%
        self.assertAlmostEqual(result["Action"]["percentage"], 66.67, places=1)
    
    def test_tie_resolution(self):
        """Test that ties are resolved alphabetically."""
        data = [
            {
                "username": "zebra",
                "movies": [{"title": "M1", "genres": ["Action"]}]
            },
            {
                "username": "alice",
                "movies": [{"title": "M2", "genres": ["Action"]}]
            }
        ]
        result = calculate_genre_superlatives(data)
        
        # alice should win because of alphabetical order
        self.assertEqual(result["Action"]["user"], "alice")
        self.assertEqual(result["Action"]["percentage"], 100.0)
    
    def test_multiple_genres_per_movie(self):
        """Test that movies with multiple genres are counted correctly."""
        data = [
            {
                "username": "user1",
                "movies": [
                    {"title": "M1", "genres": ["Action", "Sci-Fi", "Drama"]},
                    {"title": "M2", "genres": ["Comedy"]},
                ]
            }
        ]
        result = calculate_genre_superlatives(data)
        
        # Each genre should be counted once per movie
        self.assertEqual(result["Action"]["count"], 1)
        self.assertEqual(result["Sci-Fi"]["count"], 1)
        self.assertEqual(result["Drama"]["count"], 1)
        self.assertEqual(result["Comedy"]["count"], 1)
        
        # Percentages: Action, Sci-Fi, Drama = 50% (1/2), Comedy = 50% (1/2)
        self.assertEqual(result["Action"]["percentage"], 50.0)
        self.assertEqual(result["Comedy"]["percentage"], 50.0)
    
    def test_percentage_calculation(self):
        """Test that percentages are calculated correctly."""
        data = [
            {
                "username": "user1",
                "movies": [
                    {"title": "M1", "genres": ["Action"]},
                    {"title": "M2", "genres": ["Action"]},
                    {"title": "M3", "genres": ["Drama"]},
                    {"title": "M4", "genres": ["Drama"]},
                    {"title": "M5", "genres": ["Drama"]},
                ]
            }
        ]
        result = calculate_genre_superlatives(data)
        
        # Action: 2/5 = 40%
        self.assertEqual(result["Action"]["percentage"], 40.0)
        # Drama: 3/5 = 60%
        self.assertEqual(result["Drama"]["percentage"], 60.0)
    
    def test_format_text(self):
        """Test text formatting."""
        superlatives = {
            "Action": {"user": "alice", "percentage": 65.5, "count": 10, "total_movies": 15},
            "Drama": {"user": "bob", "percentage": 42.8, "count": 5, "total_movies": 12},
        }
        
        result = format_genre_superlatives(superlatives, "text")
        
        self.assertIn("Action: alice (65.50%)", result)
        self.assertIn("Drama: bob (42.80%)", result)
        self.assertIn("Superlatives by Genre:", result)
    
    def test_format_detailed(self):
        """Test detailed formatting."""
        superlatives = {
            "Action": {"user": "alice", "percentage": 65.0, "count": 13, "total_movies": 20},
        }
        
        result = format_genre_superlatives(superlatives, "detailed")
        
        self.assertIn("GENRE SUPERLATIVES - Detailed Report", result)
        self.assertIn("Genre: Action", result)
        self.assertIn("Champion: alice", result)
        self.assertIn("Percentage: 65.00%", result)
        self.assertIn("Count: 13 out of 20 total movies", result)
    
    def test_format_json(self):
        """Test JSON formatting."""
        superlatives = {
            "Action": {"user": "alice", "percentage": 65.0, "count": 13, "total_movies": 20},
        }
        
        result = format_genre_superlatives(superlatives, "json")
        
        # Should be valid JSON
        import json
        parsed = json.loads(result)
        self.assertEqual(parsed["Action"]["user"], "alice")
        self.assertEqual(parsed["Action"]["percentage"], 65.0)
    
    def test_format_invalid_type(self):
        """Test that invalid format type raises error."""
        superlatives = {"Action": {"user": "alice", "percentage": 65.0}}
        
        with self.assertRaises(ValueError):
            format_genre_superlatives(superlatives, "invalid_format")
    
    def test_user_genre_profile(self):
        """Test getting individual user genre profile."""
        result = get_user_genre_profile(self.sample_data, "alice")
        
        self.assertIsInstance(result, dict)
        self.assertIn("Action", result)
        self.assertIn("Sci-Fi", result)
        
        # alice has 2 Action movies out of 4 total = 50%
        self.assertEqual(result["Action"]["count"], 2)
        self.assertEqual(result["Action"]["percentage"], 50.0)
    
    def test_user_genre_profile_not_found(self):
        """Test getting profile for non-existent user."""
        result = get_user_genre_profile(self.sample_data, "nonexistent")
        self.assertEqual(result, {})
    
    def test_user_genre_profile_no_movies(self):
        """Test getting profile for user with no movies."""
        data = [{"username": "empty", "movies": []}]
        result = get_user_genre_profile(data, "empty")
        self.assertEqual(result, {})
    
    def test_competitive_scenario(self):
        """Test a competitive scenario with close percentages."""
        data = [
            {
                "username": "action_fan",
                "movies": [
                    {"title": "M1", "genres": ["Action"]},
                    {"title": "M2", "genres": ["Action"]},
                    {"title": "M3", "genres": ["Drama"]},
                ]
            },
            {
                "username": "balanced_viewer",
                "movies": [
                    {"title": "M4", "genres": ["Action"]},
                    {"title": "M5", "genres": ["Drama"]},
                    {"title": "M6", "genres": ["Comedy"]},
                ]
            },
        ]
        result = calculate_genre_superlatives(data)
        
        # action_fan has 66.67% Action, balanced_viewer has 33.33%
        self.assertEqual(result["Action"]["user"], "action_fan")
        self.assertAlmostEqual(result["Action"]["percentage"], 66.67, places=1)
    
    def test_all_genres_represented(self):
        """Test that all genres present in data are in results."""
        genres_in_data = set()
        for user in self.sample_data:
            for movie in user["movies"]:
                genres_in_data.update(movie.get("genres", []))
        
        result = calculate_genre_superlatives(self.sample_data)
        
        # All genres should be in results
        for genre in genres_in_data:
            self.assertIn(genre, result, f"Genre {genre} not in results")


class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios that simulate real usage."""
    
    def test_realistic_data(self):
        """Test with realistic user data."""
        data = [
            {
                "username": "horror_enthusiast",
                "movies": [
                    {"title": "The Shining", "genres": ["Horror", "Thriller"]},
                    {"title": "Hereditary", "genres": ["Horror", "Drama"]},
                    {"title": "A Quiet Place", "genres": ["Horror", "Sci-Fi"]},
                    {"title": "The Conjuring", "genres": ["Horror", "Thriller"]},
                    {"title": "Get Out", "genres": ["Horror", "Thriller"]},
                ]
            },
            {
                "username": "casual_viewer",
                "movies": [
                    {"title": "The Avengers", "genres": ["Action", "Sci-Fi"]},
                    {"title": "The Shining", "genres": ["Horror", "Thriller"]},
                    {"title": "The Notebook", "genres": ["Romance", "Drama"]},
                    {"title": "Toy Story", "genres": ["Animation", "Comedy"]},
                    {"title": "Inception", "genres": ["Action", "Sci-Fi"]},
                ]
            },
        ]
        
        result = calculate_genre_superlatives(data)
        
        # horror_enthusiast should dominate Horror
        self.assertEqual(result["Horror"]["user"], "horror_enthusiast")
        self.assertEqual(result["Horror"]["percentage"], 100.0)
        
        # Thriller should also go to horror_enthusiast (60%)
        self.assertEqual(result["Thriller"]["user"], "horror_enthusiast")
        self.assertEqual(result["Thriller"]["percentage"], 60.0)


def run_tests():
    """Run all tests and print results."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test cases
    suite.addTests(loader.loadTestsFromTestCase(TestGenreSuperlatives))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 70)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
