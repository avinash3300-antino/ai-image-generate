"""
Fetcher module — handles all HTTP calls to the travel product APIs.
Uses httpx async client for non-blocking network requests.
"""

import httpx

from config import CITIES_API, PRODUCT_API


async def fetch_cities(product_type: str) -> list[dict]:
    """
    Fetch available cities for a given product type.
    API returns nested structure: data.data.options[] where each option
    has countryName and cities[] array. We flatten this into a list of
    {city_id, city_name, country_name} dicts.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            CITIES_API,
            params={"productType": product_type},
        )
        response.raise_for_status()
        data = response.json()

    # Navigate the nested response: data.data.options[]
    try:
        options = data["data"]["data"]["options"]
    except (KeyError, TypeError):
        print("[WARN] Unexpected cities API response structure")
        return []

    # Flatten countries → cities into a simple list
    cities: list[dict] = []
    for country in options:
        country_name = country.get("countryName", "")
        for city in country.get("cities", []):
            cities.append({
                "city_id": str(city.get("id", "")),
                "city_name": city.get("name", "Unknown"),
                "country_name": country_name,
            })

    return cities


async def fetch_products(
    product_type: str,
    city_id: str,
    city_name: str,
    country_name: str,
) -> list[dict]:
    """
    Fetch products for a specific city and product type.
    Products come back with fields: name, city, country, normalPrice,
    salePrice, currency, url, image, productId, etc.
    We attach city_name and country_name for prompt building.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            PRODUCT_API,
            params={
                "productType": product_type,
                "cityId": city_id,
                "cityName": city_name,
                "countryName": country_name,
            },
        )
        response.raise_for_status()
        data = response.json()

    products: list[dict] = data.get("products", [])

    # Ensure city/country metadata is on every product
    for product in products:
        product.setdefault("city_name", city_name)
        product.setdefault("country_name", country_name)

    return products
