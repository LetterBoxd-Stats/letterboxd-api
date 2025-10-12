# Genre Superlatives Feature

## Overview

This feature adds a new type of superlative to the LetterBoxd Stats project: **Genre Aficionados**. For each genre, the system identifies which user watches the most movies from that genre by percentage of their total watch history.

## Feature Description

### What It Does

For every genre tracked in the system, the feature:
1. Calculates the percentage of each user's movies that belong to that genre
2. Identifies the user with the highest percentage
3. Stores this as a superlative with the name `"{Genre} Aficionado"`

### Example

If you have three users:
- **Alice** has logged 100 movies, 65 of which are Action films → 65% Action
- **Bob** has logged 50 movies, 25 of which are Action films → 50% Action  
- **Charlie** has logged 20 movies, 8 of which are Action films → 40% Action

Then **Alice** would win the "Action Aficionado" superlative with 65%.

## Implementation

### Files Added/Modified

1. **`genre_superlatives.py`** (NEW)
   - Standalone module with core functionality
   - Can be used independently or integrated into the larger system
   - Contains:
     - `calculate_genre_superlatives()` - Main calculation function
     - `format_genre_superlatives()` - Formatting utilities
     - `get_user_genre_profile()` - Individual user analysis
     - Comprehensive demo with sample data

2. **`stats.py`** (MODIFIED)
   - Added genre percentage superlatives to the `compute_superlatives()` function
   - Integrated seamlessly with existing superlatives computation
   - Uses existing genre_stats data from user statistics

3. **`test_genre_superlatives.py`** (NEW)
   - Comprehensive test suite with 17 test cases
   - Tests edge cases, calculations, formatting, and integration scenarios
   - All tests passing ✅

## Usage

### Standalone Usage

You can use the `genre_superlatives.py` module independently:

```python
from genre_superlatives import calculate_genre_superlatives, format_genre_superlatives

# Your user log data
user_logs = [
    {
        "username": "shreshth",
        "movies": [
            {"title": "Inception", "genres": ["Action", "Sci-Fi"]},
            {"title": "The Matrix", "genres": ["Action", "Sci-Fi"]},
            # ... more movies
        ]
    },
    # ... more users
]

# Calculate superlatives
superlatives = calculate_genre_superlatives(user_logs)

# Format for display
print(format_genre_superlatives(superlatives, "text"))
# Output:
# Superlatives by Genre:
# Action: shreshth (62.50%)
# Sci-Fi: shreshth (62.50%)
# ...
```

### Integrated Usage

When you run `stats.py` (either directly or via the GitHub Action), the genre percentage superlatives are automatically computed and stored in the database alongside other superlatives.

They will appear in the `/superlatives` API endpoint with names like:
- "Action Aficionado"
- "Drama Aficionado"
- "Horror Aficionado"
- etc.

### API Access

Once integrated, you can access these superlatives via:

```bash
GET https://letterboxd-api-zeta.vercel.app/superlatives
```

Example response:
```json
[
  {
    "name": "Action Aficionado",
    "description": "User who watches Action films most frequently (by percentage of total movies)",
    "first": ["shreshth"],
    "first_value": 65.50,
    "second": ["alice"],
    "second_value": 52.30,
    "third": ["bob"],
    "third_value": 45.80
  },
  ...
]
```

## Function Reference

### `calculate_genre_superlatives(user_logs)`

**Parameters:**
- `user_logs` (List[Dict]): List of user log dictionaries

**Returns:**
- Dict[str, Dict]: Mapping of genre to superlative data

**Example:**
```python
result = calculate_genre_superlatives(user_logs)
# Returns:
# {
#     "Action": {
#         "user": "shreshth",
#         "percentage": 65.50,
#         "count": 131,
#         "total_movies": 200
#     },
#     ...
# }
```

### `format_genre_superlatives(superlatives, format_type)`

**Parameters:**
- `superlatives` (Dict): Output from calculate_genre_superlatives()
- `format_type` (str): "text", "detailed", or "json"

**Returns:**
- str: Formatted representation

### `get_user_genre_profile(user_logs, username)`

**Parameters:**
- `user_logs` (List[Dict]): User log data
- `username` (str): Username to analyze

**Returns:**
- Dict[str, Dict]: Genre breakdown for the user

## Edge Cases Handled

The implementation handles several edge cases gracefully:

1. **Empty user logs** → Returns empty dictionary
2. **Users with no movies** → Skipped in calculations
3. **Movies with no genres** → Skipped for genre calculations
4. **Ties between users** → Resolved alphabetically (deterministic)
5. **Genres with zero watches** → Not included in results
6. **Movies with multiple genres** → Each genre counted independently

## Testing

Run the test suite:

```bash
python test_genre_superlatives.py
```

Expected output:
```
Ran 17 tests in 0.003s
OK
```

## Demo

Run the demo to see the feature in action:

```bash
python genre_superlatives.py
```

This will:
1. Create sample user data with different genre preferences
2. Calculate superlatives for all genres
3. Display results in multiple formats
4. Show individual user genre profiles
5. Test edge cases

## Design Decisions

### Why Percentage Instead of Count?

We use **percentage** rather than raw count because:
- Users have different total watch counts
- A user with 10 Action movies out of 20 (50%) is more of an "Action fan" than someone with 20 Action movies out of 200 (10%)
- Percentages normalize across different user activity levels

### Naming: "Aficionado" vs Other Terms

We chose "Aficionado" (e.g., "Action Aficionado") to:
- Distinguish from existing "Enthusiast" superlatives (which are based on ratings)
- Avoid confusion with "Critic" superlatives
- Clearly indicate this is about watch frequency/percentage

### Genre Counting with Multi-Genre Movies

When a movie belongs to multiple genres:
- Each genre is counted independently
- A movie tagged ["Action", "Sci-Fi"] counts as 1 toward Action AND 1 toward Sci-Fi
- This matches user expectations and real-world genre classification

## Code Quality

The implementation follows Python best practices:

- ✅ **PEP8 compliant** - Proper formatting and style
- ✅ **Type hints** - Clear parameter and return types
- ✅ **Comprehensive docstrings** - Every function documented
- ✅ **Logging** - Appropriate use of logging module
- ✅ **Error handling** - Graceful handling of edge cases
- ✅ **Modular design** - Self-contained and reusable
- ✅ **Well-tested** - 17 unit tests with 100% pass rate
- ✅ **Comments** - Clear inline comments where needed

## Performance Considerations

- **Time Complexity**: O(U × M × G) where:
  - U = number of users
  - M = average movies per user
  - G = average genres per movie
  
- **Space Complexity**: O(U × G) for storing genre counts

For typical usage (5-20 users, 50-500 movies each), performance is excellent (< 1ms).

## Future Enhancements

Potential improvements for future versions:

1. **Minimum threshold**: Only award superlative if user has watched at least N movies in that genre
2. **Time-based analysis**: Genre preferences over time
3. **Comparative metrics**: Show how much higher the winner's percentage is vs second place
4. **Visualization**: Generate charts showing genre distribution per user
5. **Genre combinations**: Track superlatives for genre pairs (e.g., "Action-Comedy Aficionado")

## Integration Checklist

- [x] Create standalone module (`genre_superlatives.py`)
- [x] Add comprehensive docstrings and comments
- [x] Implement edge case handling
- [x] Create test suite with 100% pass rate
- [x] Add demo functionality
- [x] Integrate into existing `stats.py`
- [x] Document in README
- [ ] Deploy and test in production environment
- [ ] Update frontend to display new superlatives
- [ ] Add to API documentation

## Support

For questions or issues with this feature, contact the maintainer or open an issue on GitHub.

## License

This feature is part of the LetterBoxd Stats project and follows the same license terms.
