"""Domain layer (pure Python, no Qt imports)."""

# Standard Yahoo 9-category H2H stat categories (SPEC: 9-cat, unweighted).
CATEGORIES: tuple[str, ...] = (
    "points",
    "rebounds",
    "assists",
    "steals",
    "blocks",
    "turnovers",
    "fg_pct",
    "ft_pct",
    "three_points",
)

__all__ = ["CATEGORIES"]
