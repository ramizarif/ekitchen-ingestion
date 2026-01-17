# Environment Configuration Guide

The autonomous recipe processor can be configured to work with different eKitchen environments through the `local.env` file.

## Configuration Options

### Production Environment (Default)
```bash
# local.env
EKITCHEN_BASE_URL=https://ekitchen-production.up.railway.app
EKITCHEN_ADMIN_EMAIL=ekitchen_tester_admin_user@example.com
EKITCHEN_ADMIN_PASSWORD=securepassword123
OPENAI_API_KEY=your_openai_api_key_here
```

### Local Development Environment
```bash
# local.env
EKITCHEN_BASE_URL=http://localhost:8080
EKITCHEN_ADMIN_EMAIL=admin@localhost
EKITCHEN_ADMIN_PASSWORD=localpassword
OPENAI_API_KEY=your_openai_api_key_here
```

### Staging Environment
```bash
# local.env
EKITCHEN_BASE_URL=https://ekitchen-staging.up.railway.app
EKITCHEN_ADMIN_EMAIL=staging_admin@example.com
EKITCHEN_ADMIN_PASSWORD=stagingpassword
OPENAI_API_KEY=your_openai_api_key_here
```

## Environment Files

- **`local.env`** - Your active configuration (git-ignored)
- **`local.env.development.example`** - Template for local development setup

## Switching Environments

### Method 1: Edit local.env directly
```bash
# Edit the file
nano local.env

# Change the EKITCHEN_BASE_URL line
EKITCHEN_BASE_URL=http://localhost:8080
```

### Method 2: Use different config files
```bash
# Create environment-specific files
cp local.env local.env.production
cp local.env.development.example local.env.development

# Switch by copying
cp local.env.development local.env  # Switch to development
cp local.env.production local.env   # Switch to production
```

## Verification

Test your configuration:
```bash
python3 -c "
import sys
import os
sys.path.append('src/processing')
from ingredient_processor_direct import DirectIngredientProcessor

processor = DirectIngredientProcessor(log_to_file=False)
print(f'Base URL: {processor.ekitchen_base_url}')
print(f'Admin Email: {processor.env_config.get(\"EKITCHEN_ADMIN_EMAIL\")}')
"
```

## Usage Examples

```bash
# Production processing (default)
python3 batch_recipe_processor.py cuisines/thai/recipes.json ./thai-images

# After switching to local development
# (Edit local.env to point to localhost:8080)
python3 batch_recipe_processor.py cuisines/thai/recipes.json ./thai-images
```

The system will automatically use the configured environment for all operations:
- Ingredient searching and creation
- Recipe creation
- Image uploads
- Authentication

## Security Notes

- Never commit `local.env` files with real credentials
- Use environment-specific credentials for each environment
- The `local.env` file is already in `.gitignore` for security