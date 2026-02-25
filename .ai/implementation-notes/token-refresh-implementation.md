# Token Refresh Implementation

## Summary

Implemented automatic token refresh system to prevent 401 Unauthorized errors when authentication tokens expire during recipe imports.

## Changes Made

### 1. DirectIngredientProcessor (`services/ingredient_processor.py`)

**New Instance Variables:**
- `self.refresh_token` - Stores refresh token alongside access token

**Updated Methods:**
- `authenticate_ekitchen()` - Now stores both `access_token` and `refresh_token` from login response
- Added debug logging for refresh token storage

**New Method: `refresh_authentication()`**
```python
def refresh_authentication(self) -> bool:
    """Refresh authentication tokens using the refresh token"""
```

**Features:**
- Calls `POST /auth/refresh` endpoint with current refresh token
- Updates both `access_token` AND `refresh_token` (both returned by API)
- Handles nested response structure (`result['data']` or direct `result`)
- Clears tokens if refresh fails with 401 (expired refresh token)
- Returns `True` on success, `False` on failure

### 2. DirectRecipeProcessor (`services/recipe_processor.py`)

**New Instance Variables:**
- `self.ekitchen_refresh_token` - Mirrors refresh token from ingredient processor

**Updated Methods:**
- `_initialize_apis()` - Now syncs refresh token from ingredient processor after authentication

**New Method: `_refresh_ekitchen_tokens()`**
```python
def _refresh_ekitchen_tokens(self) -> bool:
    """Refresh eKitchen authentication tokens before API calls"""
```

**Features:**
- Delegates to `ingredient_processor.refresh_authentication()`
- Syncs updated tokens back to local variables
- Called automatically before recipe creation

**Modified Methods:**
- `create_ekitchen_recipe()` - Now calls `_refresh_ekitchen_tokens()` BEFORE making API request

## Strategy: Always Refresh

We implemented the **"Always Refresh"** strategy recommended in the requirements:

```python
def create_ekitchen_recipe(...):
    # 1. Refresh tokens FIRST
    self._refresh_ekitchen_tokens()

    # 2. Create recipe with fresh token
    response = requests.post(
        f"{base_url}/global-recipes",
        headers={'Authorization': f'Bearer {self.ekitchen_token}'},
        ...
    )
```

**Why this strategy?**
- Guarantees fresh tokens for every import
- Prevents 401 errors even after idle periods
- Simple and reliable - no retry logic needed
- Minimal performance impact (refresh is fast)

## Response Format

The `/auth/refresh` endpoint returns:
```json
{
  "success": true,
  "data": {
    "access_token": "new_access_token_here",
    "refresh_token": "new_refresh_token_here"
  }
}
```

Both tokens are updated on every refresh.

## Error Handling

### Missing Refresh Token
If no refresh token is available (shouldn't happen after initial auth):
- Logs warning: "⚠️  No refresh token available, skipping token refresh"
- Returns `False` but doesn't fail the request
- Uses existing access token (may still work if not expired)

### Expired Refresh Token (401)
If refresh fails with 401 Unauthorized:
- Logs warning: "⚠️  Refresh token expired, clearing tokens"
- Clears both `access_token` and `refresh_token`
- Next request will fail with "❌ Not authenticated with eKitchen"
- User must re-authenticate (restart service or re-login)

### Network Errors
If refresh fails due to network/timeout:
- Logs error with details
- Returns `False`
- Uses existing tokens (may fail if expired)

## Testing Verification

After deployment, verify:

1. **Imports work after idle periods:**
   - Let service sit idle for 1+ hours
   - Attempt recipe import
   - Should succeed (tokens refreshed automatically)

2. **Tokens are being refreshed:**
   - Check logs for "🔄 Refreshing authentication tokens..."
   - Check logs for "✅ Token refresh successful"
   - Verify new token lengths in debug logs

3. **Both tokens updated:**
   - Verify both access_token and refresh_token are stored
   - Check debug logs: "DEBUG: New refresh token stored (length: XXX)"

4. **Subsequent imports continue working:**
   - Import multiple recipes in sequence
   - Each should refresh tokens before creation
   - No 401 errors should occur

## Log Messages

**Success Flow:**
```
🔄 Refreshing authentication tokens...
DEBUG: Using base URL: https://ekitchen-production.up.railway.app
✅ Token refresh successful
DEBUG: New access token length: 147
DEBUG: New refresh token stored (length: 147)
🏗️  Creating recipe in eKitchen: Recipe Name
```

**Warning (no refresh token):**
```
⚠️  No refresh token available, skipping token refresh
🏗️  Creating recipe in eKitchen: Recipe Name
```

**Error (expired refresh token):**
```
❌ HTTP Error during token refresh: 401 Unauthorized
⚠️  Refresh token expired, clearing tokens
❌ Not authenticated with eKitchen
```

## Code References

**Token storage:**
- `services/ingredient_processor.py:98` - `self.refresh_token` declaration
- `services/ingredient_processor.py:240` - Store refresh token from login
- `services/recipe_processor.py:51` - `self.ekitchen_refresh_token` declaration
- `services/recipe_processor.py:163` - Sync refresh token on init

**Refresh implementation:**
- `services/ingredient_processor.py:259-314` - `refresh_authentication()` method
- `services/recipe_processor.py:1183-1195` - `_refresh_ekitchen_tokens()` method
- `services/recipe_processor.py:1204` - Call refresh before recipe creation

## Deployment

Committed in: `2fb0350` - "feat: Implement automatic token refresh before API calls"
Deployed to: `development` branch (production)
