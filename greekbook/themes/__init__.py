# -*- coding: utf-8 -*-
from .base import Theme
from .sepia import SepiaTheme
from .clean import CleanTheme
from .academic import AcademicTheme

_REGISTRY = {
    "sepia": SepiaTheme,
    "clean": CleanTheme,
    "academic": AcademicTheme,
}


def get_theme(name: str) -> type:
    try:
        return _REGISTRY[name]
    except KeyError:
        supported = ", ".join(sorted(_REGISTRY))
        raise ValueError(f"Άγνωστο theme '{name}'. Διαθέσιμα themes: {supported}")


def available_themes():
    return sorted(_REGISTRY)


__all__ = ["Theme", "SepiaTheme", "CleanTheme", "AcademicTheme", "get_theme", "available_themes"]
