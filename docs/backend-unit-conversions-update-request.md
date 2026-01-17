# Backend Update Request: Add unit_conversions and purchase_info to Ingredient Update API

## Problem
The `/api/global-ingredients/{id}` PATCH endpoint currently doesn't accept `unit_conversions` and `purchase_info` fields in the update request, but these fields exist in the database and need to be updatable.

## Current Issue Example
Artichoke heart ingredient (id: `d2ke039peops73cbving`) has incorrect unit conversion:
- Current: `"can": 0.04` (means 1 can = 0.04 oz, which is wrong)
- Should be: `"can": 14` (1 can = 14 oz, matching the purchase_quantity)

## Required Changes

### 1. Backend API Update
Please update the global ingredients PATCH endpoint to accept these fields:

```typescript
// Add to the ingredient update DTO/interface
{
  // ... existing fields ...
  unit_conversions?: string | object;  // JSON string or object with unit conversion factors
  purchase_info?: string | object;     // JSON string or object with purchase details
}
```

### 2. Database Update Handler
Ensure the update handler properly processes these fields:

```typescript
// In the update service/handler
if (updateData.unit_conversions) {
  // If it's an object, stringify it
  const conversions = typeof updateData.unit_conversions === 'object'
    ? JSON.stringify(updateData.unit_conversions)
    : updateData.unit_conversions;

  // Update in database
  updates.unit_conversions = conversions;
}

if (updateData.purchase_info) {
  // If it's an object, stringify it
  const info = typeof updateData.purchase_info === 'object'
    ? JSON.stringify(updateData.purchase_info)
    : updateData.purchase_info;

  // Update in database
  updates.purchase_info = info;
}
```

### 3. MCP Server Update
After the backend is updated, also update the eKitchen MCP server's `update_global_ingredient` tool to include these fields in the request body.

## Testing
Once updated, we should be able to fix the artichoke heart conversion with:

```python
# Via MCP
mcp__ekitchen__update_global_ingredient(
  id="d2ke039peops73cbving",
  unit_conversions={"cup": 8.35, "can": 14, "g": 0.035274, "oz": 1.0, "ounce": 1.0}
)
```

## Priority
This is needed to fix ingredient data accuracy issues in production. The artichoke heart is just one example - there may be other ingredients with similar conversion issues that need correction.