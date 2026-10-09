"""Domain layer (pure Python, no Qt imports)."""

# Standard Yahoo 9-category H2H stat categories (SPEC: 9-cat, unweighted).
CATEGORIES: tuple[str, ...] = (
    "fg_pct",
    "ft_pct",
    "three_points",
    "points",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
)

__all__ = ["CATEGORIES"]
