# 🧪 Quick Test Guide - Recipe Discovery MCP

## 📁 File Organization

```
tests/user_experience/
├── __init__.py                     # Package info and documentation
├── test_basic_functionality.py    # Simple validation tests
├── test_comprehensive_features.py # Full feature demonstration
├── test_individual_commands.py    # Copy-paste test commands
├── test_interactive_demos.py      # Guided demonstrations
└── quick_test_guide.md            # This guide
```

## 🚀 Quick Start

**IMPORTANT: Always activate the virtual environment first!**

### 1. Basic Functionality Test (1 minute)
```bash
cd /Users/ramiz/ekitchen/ekitchen-ingestion
source venv/bin/activate
python3 tests/user_experience/test_basic_functionality.py
```

### 2. Interactive Demo (5-10 minutes)
```bash
source venv/bin/activate
python3 tests/user_experience/test_interactive_demos.py
```

### 3. Comprehensive Feature Test (3 minutes)
```bash
source venv/bin/activate
python3 tests/user_experience/test_comprehensive_features.py
```

## ⚡ Instant Copy-Paste Commands

### Get All Copy-Paste Commands:
```bash
python3 tests/user_experience/test_individual_commands.py
```

### Get Quick Commands Only:
```bash
python3 tests/user_experience/test_individual_commands.py quick
```

## 🎯 Common Test Scenarios

### Test Single Recipe (30 seconds)
```bash
source venv/bin/activate && python3 -c "
import asyncio
from recipe_discovery_mcp.scraper import RecipeScrapingService
async def test():
    scraper = RecipeScrapingService()
    recipe = await scraper.scrape_recipe('https://www.allrecipes.com/recipe/16354/easy-meatloaf/')
    print(f'✅ {recipe.title}: {len(recipe.ingredients)} ingredients')
asyncio.run(test())
"
```

### Check Available Sites (5 seconds)
```bash
source venv/bin/activate && python3 -c "
from recipe_discovery_mcp.site_manager import SiteManager
sm = SiteManager()
for site in sm.get_enabled_sites():
    print(f'• {site.name} ({site.domain}) - {site.priority} priority')
"
```

### Test Multi-Site Discovery (2 minutes)
```bash
source venv/bin/activate && python3 -c "
import asyncio
from recipe_discovery_mcp.discovery_engine import MultiSiteDiscoveryEngine
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.http_client import AsyncHttpClient
from recipe_discovery_mcp.scraper import RecipeScrapingService
from recipe_discovery_mcp.models import DiscoveryConfig

async def test():
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    scraper = RecipeScrapingService()
    discovery_engine = MultiSiteDiscoveryEngine(site_manager, url_manager, scraper)
    
    config = DiscoveryConfig(max_urls_per_site=3, target_sites=['allrecipes.com'], validate_urls=True, max_total_concurrent=2)
    result = await discovery_engine.discover_recipes('chicken recipe', config)
    
    successful = result.get_successful_recipes()
    print(f'🎯 Found {len(successful)} successful recipes')
    for i, recipe in enumerate(successful[:3], 1):
        print(f'{i}. {recipe.title} - {len(recipe.ingredients)} ingredients')
    
    await http_client.close()

asyncio.run(test())
"
```

## 🎬 Interactive Demos

### Run Quick Demo (3 minutes)
```bash
python3 tests/user_experience/test_interactive_demos.py quick
```

### Run Full Interactive Menu
```bash
python3 tests/user_experience/test_interactive_demos.py
```

### Available Demo Options:
1. **Basic Introduction** - System overview and configuration
2. **Single Recipe Extraction** - Extract one recipe with detailed output
3. **Batch Processing** - Process multiple recipes simultaneously
4. **Multi-Site Discovery Engine** - Full discovery across multiple sites
5. **Error Handling & Recovery** - Test error scenarios
6. **Performance Monitoring** - View statistics and health metrics

## 📊 Test Categories

### 🔧 Developer Testing
- **Unit Tests**: `pytest tests/unit/`
- **Integration Tests**: `pytest tests/integration/`
- **Comprehensive**: `pytest tests/`

### 👥 User Experience Testing
- **Quick Validation**: `test_basic_functionality.py`
- **Feature Showcase**: `test_comprehensive_features.py`
- **Copy-Paste Commands**: `test_individual_commands.py`
- **Guided Demos**: `test_interactive_demos.py`

## 🏃‍♂️ Test Suites

### Fastest (30 seconds)
```bash
python3 tests/user_experience/test_individual_commands.py quick
```

### Quick (1 minute)
```bash
python3 tests/user_experience/test_basic_functionality.py
```

### Comprehensive (3 minutes)
```bash
python3 tests/user_experience/test_comprehensive_features.py
```

### Interactive (5-10 minutes)
```bash
python3 tests/user_experience/test_interactive_demos.py
```

## 🎯 Test What You Need

### I want to test a specific URL:
```bash
python3 -c "
import asyncio
from recipe_discovery_mcp.scraper import RecipeScrapingService
async def test():
    scraper = RecipeScrapingService()
    url = input('Enter recipe URL: ')
    recipe = await scraper.scrape_recipe(url)
    if recipe.success:
        print(f'✅ {recipe.title}: {len(recipe.ingredients)} ingredients')
    else:
        print(f'❌ Failed: {recipe.error_message}')
asyncio.run(test())
"
```

### I want to test a custom search:
```bash
python3 -c "
import asyncio
from recipe_discovery_mcp.url_manager import UrlManager
from recipe_discovery_mcp.site_manager import SiteManager
from recipe_discovery_mcp.http_client import AsyncHttpClient
async def test():
    http_client = AsyncHttpClient()
    site_manager = SiteManager()
    url_manager = UrlManager(site_manager, http_client)
    query = input('Enter search query: ')
    urls = await url_manager.discover_recipe_urls(query, max_urls_per_site=5)
    for site, url_list in urls.items():
        if url_list: print(f'{site}: {len(url_list)} URLs')
    await http_client.close()
asyncio.run(test())
"
```

### I want to check system health:
```bash
python3 -c "
import asyncio
from recipe_discovery_mcp.scraper import RecipeScrapingService
async def test():
    scraper = RecipeScrapingService()
    await scraper.scrape_recipe('https://www.allrecipes.com/recipe/16354/easy-meatloaf/')
    stats = scraper.get_stats()
    for key, value in stats.items(): print(f'{key}: {value}')
asyncio.run(test())
"
```

## 🔍 Available Recipe Sites

Your system is configured with these sites:
- **AllRecipes** (allrecipes.com) - High priority
- **Food Network** (foodnetwork.com) - High priority
- **Epicurious** (epicurious.com) - Medium priority
- **BBC Good Food** (bbcgoodfood.com) - Medium priority
- **Taste.com.au** (taste.com.au) - Low priority

## 💡 Tips

- **Start with quick tests** to verify basic functionality
- **Use interactive demos** for comprehensive understanding
- **Copy-paste commands** for immediate testing needs
- **All tests work with real websites** - some URLs may fail (this is normal)
- **Adjust concurrency and batch sizes** based on your needs
- **Check the logs** for detailed operation information

## 🚀 Ready to Test?

Choose your approach:
1. **New to the system?** → Start with `test_interactive_demos.py`
2. **Want quick validation?** → Use `test_basic_functionality.py`
3. **Need specific commands?** → Check `test_individual_commands.py`
4. **Want full showcase?** → Run `test_comprehensive_features.py`

Happy testing! 🎉