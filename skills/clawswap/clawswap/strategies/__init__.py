"""ClawSwap strategy templates."""
from .mean_reversion import MeanReversionStrategy, MeanReversionConfig
from .momentum import MomentumStrategy, MomentumConfig
from .grid import GridStrategy, GridConfig

STRATEGY_MAP = {
    "mean_reversion": (MeanReversionStrategy, MeanReversionConfig),
    "momentum": (MomentumStrategy, MomentumConfig),
    "grid": (GridStrategy, GridConfig),
}

__all__ = [
    "MeanReversionStrategy", "MeanReversionConfig",
    "MomentumStrategy", "MomentumConfig",
    "GridStrategy", "GridConfig",
    "STRATEGY_MAP",
]
