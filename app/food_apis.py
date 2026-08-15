"""
Free public food-database lookups.

Used as a fallback / precision-boost path alongside the Gemini vision flow:
- Open Food Facts: barcode -> packaged product macros (no API key required).
- USDA FoodData Central: raw ingredient name -> macros per 100g (free API key,
  the shared "DEMO_KEY" works for light usage, or the user can set their own
  in Settings for higher rate limits).

Both are plain public REST APIs -- no server of ours sits in between, so
there is nothing for us to host or pay for.
"""

import os
from dataclasses import dataclass
from typing import List, Optional

import httpx

from app.models import FoodItem, MacroBreakdown

OFF_PRODUCT_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

_NUTRIENT_NAME_MAP = {
    "protein": {"Protein"},
    "carbs": {"Carbohydrate, by difference"},
    "fat": {"Total lipid (fat)"},
    "calories": {"Energy"},
}


class FoodApiError(Exception):
    """Raised on network failure or when a lookup finds nothing."""


@dataclass
class PackagedProduct:
    """A barcode-scanned packaged product, with macros per 100g and (when
    Open Food Facts provides one) a real serving size to scale to instead --
    per_100g alone made a 500mL bottle log identically to a 100mL sample."""

    name: str
    brand: str
    per_100g: MacroBreakdown
    serving_size_g: Optional[float]
    # e.g. "500 ml" or "1 bottle (500ml)" -- Open Food Facts' own display
    # string for serving_size_g, shown alongside the scaled macros instead
    # of re-deriving a label from the raw gram figure.
    serving_size_label: Optional[str]
    # per_100g scaled by serving_size_g/100 (see MacroBreakdown.scaled) --
    # None when Open Food Facts didn't provide a serving size, in which case
    # callers fall back to per_100g and should say so.
    per_serving: Optional[MacroBreakdown]
    # True if Open Food Facts categorizes this as a water product (plain,
    # spring, mineral, or sparkling) -- lets the Lookup screen offer to log
    # it to the water tracker (via serving_size_g, treated as mL) instead
    # of the macro/calorie flow, which is pointless for a ~0-calorie item.
    is_water: bool = False


async def lookup_barcode(barcode: str) -> PackagedProduct:
    """Look up a packaged product by UPC/EAN barcode via Open Food Facts."""
    url = OFF_PRODUCT_URL.format(barcode=barcode.strip())
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise FoodApiError(f"Could not reach Open Food Facts: {exc}") from exc

    if data.get("status") != 1:
        raise FoodApiError(f"No product found for barcode {barcode}.")

    product = data["product"]
    nutriments = product.get("nutriments", {})

    macros = MacroBreakdown(
        meal_name=product.get("product_name") or "Packaged product",
        calories=round(nutriments.get("energy-kcal_100g", 0) or 0),
        protein=round(nutriments.get("proteins_100g", 0) or 0),
        carbs=round(nutriments.get("carbohydrates_100g", 0) or 0),
        fat=round(nutriments.get("fat_100g", 0) or 0),
        identified_items=[
            FoodItem(
                name=product.get("product_name") or "Packaged product",
                portion_size="100g",
            )
        ],
    )
    serving_raw = product.get("serving_quantity")
    serving_size_g = float(serving_raw) if serving_raw not in (None, "") else None
    serving_size_label = product.get("serving_size") or None

    per_serving = None
    if serving_size_g:
        factor = serving_size_g / 100.0
        per_serving = MacroBreakdown(
            meal_name=macros.meal_name,
            calories=round(macros.calories * factor),
            protein=round(macros.protein * factor),
            carbs=round(macros.carbs * factor),
            fat=round(macros.fat * factor),
            identified_items=[
                FoodItem(
                    name=product.get("product_name") or "Packaged product",
                    portion_size=serving_size_label or f"{serving_size_g:.0f}g",
                )
            ],
        )

    # "en:waters"/"en:spring-waters"/"en:mineral-waters"/"en:sparkling-waters"
    # etc -- substring match rather than an exhaustive tag list, since Open
    # Food Facts' water taxonomy has many sub-tags and new ones get added.
    # Falls back to the product name for the (rarer) case where a real water
    # product is missing category tags -- calorie-gated so a merely
    # water-flavored/named item with real macros doesn't false-positive.
    categories_tags = product.get("categories_tags") or []
    name_lower = (product.get("product_name") or "").lower()
    is_water = (
        any(tag.startswith("en:") and "water" in tag for tag in categories_tags)
        or (macros.calories == 0 and "water" in name_lower)
    )

    return PackagedProduct(
        name=product.get("product_name") or "Unknown product",
        brand=product.get("brands") or "",
        per_100g=macros,
        serving_size_g=serving_size_g,
        serving_size_label=serving_size_label,
        per_serving=per_serving,
        is_water=is_water,
    )


async def search_usda(query: str, limit: int = 5) -> List[MacroBreakdown]:
    """Search USDA FoodData Central for raw ingredients, returned as per-100g macro breakdowns."""
    api_key = os.environ.get("USDA_API_KEY", "DEMO_KEY")
    params = {"query": query, "pageSize": limit, "api_key": api_key}
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(USDA_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise FoodApiError(f"Could not reach USDA FoodData Central: {exc}") from exc

    results = []
    for food in data.get("foods", [])[:limit]:
        nutrients = {n.get("nutrientName"): n.get("value", 0) for n in food.get("foodNutrients", [])}
        results.append(
            MacroBreakdown(
                meal_name=food.get("description", query).title(),
                calories=round(_lookup_nutrient(nutrients, "calories")),
                protein=round(_lookup_nutrient(nutrients, "protein")),
                carbs=round(_lookup_nutrient(nutrients, "carbs")),
                fat=round(_lookup_nutrient(nutrients, "fat")),
                identified_items=[
                    FoodItem(name=food.get("description", query).title(), portion_size="100g")
                ],
            )
        )
    if not results:
        raise FoodApiError(f"No USDA results found for '{query}'.")
    return results


def _lookup_nutrient(nutrients: dict, macro_key: str) -> float:
    for name in _NUTRIENT_NAME_MAP[macro_key]:
        if name in nutrients:
            return float(nutrients[name])
    return 0.0
