# 🔄 Fallbacks

Just in case anything goes wrong, we've added fallbacks extending Playwright serverless functions:

```python
get_flights(
    ..., 
    fetch_mode="fallback"  # common/fallback/force-fallback
)

# ...or:

get_fights_from_filter(
    filter, 
    mode="fallback"  # common/fallback/force-fallback
)
```

There are a few modes for fallbacks:

- `common` – This uses the standard scraping process.
- `fallback` – Enables a fallback support if the standard process fails.
- `force-fallback` – Forces using the fallback.

Some flight request data are displayed upon client request, meaning it's not possible for traditional web scraping. Therefore, if we used [Playwright](https://try.playwright.tech), which uses Chromium (a browser), and fetched the inner HTML, we could make the original scraper work again! Magic :sparkles:
