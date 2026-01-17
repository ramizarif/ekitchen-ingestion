# Shopping List Optimization Implementation Guide

## Overview
This guide provides complete implementation details for backend agents to correctly convert recipe ingredients into optimized shopping list items using enriched ingredient data. The system handles unit conversions, cost calculations, and purchase optimization automatically.

## Field Definitions

### Cost Fields
- **`EstimatedCostValue`**: **Cost per single unit of `EstimatedCostUnit`**
  - Example: `3.99` means $3.99 per individual pound
  - This is the base unit cost for calculations

- **`EstimatedCostUnit`**: **The unit that the cost is expressed in**
  - Example: `"pound"` means the $3.99 is per pound
  - This matches one of the keys in `unit_conversions`

### Purchase Optimization Fields (from `purchase_info` JSON)
- **`purchase_unit`**: **The unit customers typically buy this ingredient in**
  - Example: `"pound"` - customers buy flour by the pound
  - May be different from recipe units (cups, tbsp, etc.)

- **`purchase_quantity`**: **Typical package/bulk size available for purchase**
  - Example: `5.0` - flour typically sold in 5-pound bags
  - This is NOT the minimum purchase, it's the common package size

- **`min_purchase_threshold`**: **Minimum quantity worth purchasing**
  - Example: `2.0` - don't buy less than 2 pounds (avoid tiny purchases)
  - Used for shopping list optimization logic

## Cost Calculation Logic

### Answer to Question 1: EstimatedCostValue Semantics
**Answer: (a) $3.99 per individual pound**

The enrichment script uses AI cost estimation that calculates cost per single unit. So:
- `EstimatedCostValue: 3.99, EstimatedCostUnit: "pound"` = $3.99 per 1 pound
- `EstimatedCostValue: 0.25, EstimatedCostUnit: "scoop"` = $0.25 per 1 scoop

### Answer to Question 2: Shopping List Cost Calculation
**Answer: (b) $7.98 (total cost for 2 pounds)**

For shopping list items, store the **total cost for the optimized quantity**:
```
Recipe needs: 2 cups → converts to 0.25 pounds
Min threshold: 2.0 pounds → optimize to 2 pounds
Cost calculation: 2 pounds × $3.99/pound = $7.98 total
Shopping list item: quantity=2.0, cost=$7.98
```

### Answer to Question 3: Unit Conversion and Cost Scaling
**Formula**: `final_cost = optimized_quantity × EstimatedCostValue`

Example:
```
Recipe: 2 cups flour
Unit conversion: {"cup": 0.125} (1 cup = 0.125 pounds)
Recipe in base units: 2 × 0.125 = 0.25 pounds needed
Min threshold: 2.0 pounds → optimize to 2.0 pounds
Final cost: 2.0 pounds × $3.99/pound = $7.98
```

### Answer to Question 4: Database Storage
**Store total cost for the optimized quantity**

In `shopping_list_items` table:
- `quantity`: 2.0 (optimized pounds)  
- `cost`: $7.98 (total cost for 2.0 pounds)
- `unit`: "pound"

This makes `SUM(cost * 1)` work correctly (since cost already includes quantity).

### Answer to Question 5: Test Case Validation
**Your test expectation is CORRECT**

The math should be:
```
Input: 2 cups flour (recipe requirement)
Conversion: 2 cups × 0.125 = 0.25 pounds needed
Optimization: max(0.25, min_threshold=2.0) = 2.0 pounds
Cost: 2.0 pounds × $3.99/pound = $7.98
Result: quantity=2.0, unit="pound", cost=$7.98 ✅
```

## Semantic Relationships

### `purchase_quantity` vs `min_purchase_threshold`
- **`purchase_quantity`**: "Flour comes in 5-pound bags" (package size info)
- **`min_purchase_threshold`**: "Don't buy less than 2 pounds" (optimization rule)

The `purchase_quantity` provides context but doesn't directly affect cost calculation. The `min_purchase_threshold` determines the minimum optimized quantity.

### Real-World Example: Honey
```json
{
  "EstimatedCostValue": 0.25,
  "EstimatedCostUnit": "scoop", 
  "purchase_info": {
    "purchase_unit": "bottle",
    "purchase_quantity": 24,
    "min_purchase_threshold": 4,
    "supplier": "AI Estimate"
  },
  "unit_conversions": {
    "scoop": 1.0,
    "bottle": 24.0,
    "tablespoon": 0.5
  }
}
```

**Recipe needs**: 2 tablespoons honey
**Conversion**: 2 tbsp × 0.5 = 1 scoop needed
**Optimization**: max(1, min_threshold=4) = 4 scoops
**Cost**: 4 scoops × $0.25/scoop = $1.00 total
**Shopping list**: quantity=4, unit="scoop", cost=$1.00

## Shopping List Optimization Algorithm

```python
def optimize_ingredient_for_shopping(ingredient, recipe_quantity, recipe_unit):
    # Convert recipe quantity to cost unit
    conversion_factor = ingredient.unit_conversions[recipe_unit]
    needed_in_cost_unit = recipe_quantity * conversion_factor
    
    # Apply minimum purchase threshold
    min_threshold = ingredient.purchase_info.min_purchase_threshold
    optimized_quantity = max(needed_in_cost_unit, min_threshold)
    
    # Calculate total cost
    total_cost = optimized_quantity * ingredient.EstimatedCostValue
    
    return {
        'quantity': optimized_quantity,
        'unit': ingredient.EstimatedCostUnit,
        'cost': total_cost  # Total cost for the optimized quantity
    }
```

## Key Insights for Backend Implementation

1. **Cost Storage**: Always store total cost in shopping_list_items.cost
2. **Unit Consistency**: Use EstimatedCostUnit as the base unit for all calculations  
3. **Conversion Logic**: Convert recipe units to cost units using unit_conversions
4. **Optimization**: Apply min_purchase_threshold to avoid tiny purchases
5. **Package Info**: purchase_quantity is informational (shows typical package size)

This ensures accurate cost tracking and enables intelligent shopping list optimization!

---

# Complete Implementation Guide

## Step-by-Step Implementation

### Step 1: Data Retrieval
When a user adds a recipe to their shopping list, you need to:

```go
type RecipeIngredient struct {
    IngredientID string  `json:"ingredient_id"`
    Quantity     float64 `json:"quantity"`
    Unit         string  `json:"unit"`
    Name         string  `json:"name"`
}

// Get enriched ingredient data for each recipe ingredient
func GetEnrichedIngredient(ingredientID string) (*GlobalIngredient, error) {
    // Query global_ingredients table for complete enriched data
    // Must include: EstimatedCostValue, EstimatedCostUnit, PurchaseInfo, UnitConversions
}
```

### Step 2: Parse JSON Fields
Extract purchase optimization data from JSON fields:

```go
type PurchaseInfo struct {
    PurchaseUnit          string  `json:"purchase_unit"`
    PurchaseQuantity      float64 `json:"purchase_quantity"`
    MinPurchaseThreshold  float64 `json:"min_purchase_threshold"`
    Supplier             string  `json:"supplier"`
}

type UnitConversions map[string]float64

func ParseIngredientData(ingredient *GlobalIngredient) (*PurchaseInfo, UnitConversions, error) {
    var purchaseInfo PurchaseInfo
    var unitConversions UnitConversions
    
    if err := json.Unmarshal([]byte(ingredient.PurchaseInfo), &purchaseInfo); err != nil {
        return nil, nil, fmt.Errorf("failed to parse purchase_info: %w", err)
    }
    
    if err := json.Unmarshal([]byte(ingredient.UnitConversions), &unitConversions); err != nil {
        return nil, nil, fmt.Errorf("failed to parse unit_conversions: %w", err)
    }
    
    return &purchaseInfo, unitConversions, nil
}
```

### Step 3: Core Optimization Algorithm

```go
type ShoppingListItem struct {
    IngredientID string  `json:"ingredient_id"`
    Name         string  `json:"name"`
    Quantity     float64 `json:"quantity"`
    Unit         string  `json:"unit"`
    Cost         float64 `json:"cost"`        // Total cost for this quantity
    CostPerUnit  float64 `json:"cost_per_unit"` // For display purposes
}

func OptimizeIngredientForShopping(
    recipeQuantity float64,
    recipeUnit string,
    ingredient *GlobalIngredient,
) (*ShoppingListItem, error) {
    
    // Parse enriched data
    purchaseInfo, unitConversions, err := ParseIngredientData(ingredient)
    if err != nil {
        return nil, err
    }
    
    // Step 1: Convert recipe quantity to cost unit
    conversionFactor, exists := unitConversions[recipeUnit]
    if !exists {
        return nil, fmt.Errorf("no conversion factor for unit: %s", recipeUnit)
    }
    
    neededInCostUnit := recipeQuantity * conversionFactor
    
    // Step 2: Apply minimum purchase threshold
    optimizedQuantity := math.Max(neededInCostUnit, purchaseInfo.MinPurchaseThreshold)
    
    // Step 3: Calculate total cost
    totalCost := optimizedQuantity * ingredient.EstimatedCostValue
    costPerUnit := ingredient.EstimatedCostValue
    
    return &ShoppingListItem{
        IngredientID: ingredient.ID,
        Name:         ingredient.Name,
        Quantity:     optimizedQuantity,
        Unit:         ingredient.EstimatedCostUnit,
        Cost:         totalCost,        // Store total cost
        CostPerUnit:  costPerUnit,      // For UI display
    }, nil
}
```

### Step 4: Batch Processing for Recipes

```go
func AddRecipeToShoppingList(userID string, recipe *Recipe) error {
    var shoppingItems []ShoppingListItem
    
    for _, recipeIngredient := range recipe.Ingredients {
        // Get enriched ingredient data
        ingredient, err := GetEnrichedIngredient(recipeIngredient.IngredientID)
        if err != nil {
            return fmt.Errorf("failed to get ingredient %s: %w", recipeIngredient.IngredientID, err)
        }
        
        // Skip ingredients without enrichment data
        if ingredient.EstimatedCostValue == 0 || ingredient.UnitConversions == "" {
            log.Printf("Skipping ingredient %s: insufficient enrichment data", ingredient.Name)
            continue
        }
        
        // Optimize for shopping
        item, err := OptimizeIngredientForShopping(
            recipeIngredient.Quantity,
            recipeIngredient.Unit,
            ingredient,
        )
        if err != nil {
            log.Printf("Failed to optimize ingredient %s: %v", ingredient.Name, err)
            continue
        }
        
        shoppingItems = append(shoppingItems, *item)
    }
    
    // Step 5: Consolidate duplicate ingredients
    consolidatedItems := ConsolidateShoppingItems(shoppingItems)
    
    // Step 6: Save to database
    return SaveShoppingListItems(userID, consolidatedItems)
}
```

### Step 5: Item Consolidation Logic

```go
func ConsolidateShoppingItems(items []ShoppingListItem) []ShoppingListItem {
    itemMap := make(map[string]*ShoppingListItem)
    
    for _, item := range items {
        key := fmt.Sprintf("%s_%s", item.IngredientID, item.Unit)
        
        if existing, exists := itemMap[key]; exists {
            // Combine quantities and costs
            existing.Quantity += item.Quantity
            existing.Cost += item.Cost
        } else {
            itemCopy := item
            itemMap[key] = &itemCopy
        }
    }
    
    // Convert map back to slice
    var consolidated []ShoppingListItem
    for _, item := range itemMap {
        consolidated = append(consolidated, *item)
    }
    
    return consolidated
}
```

### Step 6: Database Schema Requirements

```sql
-- Shopping list items table
CREATE TABLE shopping_list_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    ingredient_id UUID NOT NULL REFERENCES global_ingredients(id),
    name VARCHAR(255) NOT NULL,
    quantity DECIMAL(10,3) NOT NULL,      -- Optimized quantity
    unit VARCHAR(50) NOT NULL,            -- Cost unit (EstimatedCostUnit)
    cost DECIMAL(10,2) NOT NULL,          -- Total cost for this quantity
    cost_per_unit DECIMAL(10,2) NOT NULL, -- For display (EstimatedCostValue)
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Index for efficient queries
CREATE INDEX idx_shopping_list_user_ingredient ON shopping_list_items(user_id, ingredient_id);
```

## Complete Working Examples

### Example 1: Flour (Simple Case)
```
Recipe: "2 cups all-purpose flour"
Ingredient Data:
- EstimatedCostValue: 3.99
- EstimatedCostUnit: "pound"  
- UnitConversions: {"cup": 0.125, "pound": 1.0}
- MinPurchaseThreshold: 2.0

Calculation:
1. Convert: 2 cups × 0.125 = 0.25 pounds needed
2. Optimize: max(0.25, 2.0) = 2.0 pounds
3. Cost: 2.0 × $3.99 = $7.98

Result: quantity=2.0, unit="pound", cost=$7.98 ✅
```

### Example 2: Honey (Complex Units)
```
Recipe: "3 tablespoons honey"
Ingredient Data:
- EstimatedCostValue: 0.25
- EstimatedCostUnit: "scoop"
- UnitConversions: {"tablespoon": 0.5, "scoop": 1.0, "bottle": 24.0}
- MinPurchaseThreshold: 4.0

Calculation:
1. Convert: 3 tbsp × 0.5 = 1.5 scoops needed
2. Optimize: max(1.5, 4.0) = 4.0 scoops  
3. Cost: 4.0 × $0.25 = $1.00

Result: quantity=4.0, unit="scoop", cost=$1.00 ✅
```

### Example 3: Consolidation Across Multiple Recipes
```
Recipe A: "1 cup flour" → 2.0 pounds, $7.98
Recipe B: "0.5 cups flour" → 2.0 pounds, $7.98 
Consolidated: 4.0 pounds, $15.96 total
```

## Error Handling & Edge Cases

### Missing or Invalid Data
```go
func ValidateIngredientData(ingredient *GlobalIngredient) error {
    if ingredient.EstimatedCostValue <= 0 {
        return fmt.Errorf("invalid cost value: %f", ingredient.EstimatedCostValue)
    }
    
    if ingredient.EstimatedCostUnit == "" {
        return fmt.Errorf("missing cost unit")
    }
    
    if ingredient.UnitConversions == "" {
        return fmt.Errorf("missing unit conversions")
    }
    
    if ingredient.PurchaseInfo == "" {
        return fmt.Errorf("missing purchase info")
    }
    
    return nil
}
```

### Unit Conversion Fallbacks
```go
func GetConversionFactor(unitConversions UnitConversions, fromUnit, toUnit string) (float64, error) {
    // Direct conversion
    if factor, exists := unitConversions[fromUnit]; exists {
        return factor, nil
    }
    
    // Common fallbacks for missing conversions
    fallbacks := map[string]float64{
        "tsp":        0.02,   // Approximate for volume
        "tbsp":       0.06,   
        "cup":        0.125,  
        "piece":      0.5,    // Approximate for count-based
        "serving":    0.5,
    }
    
    if factor, exists := fallbacks[fromUnit]; exists {
        log.Printf("Using fallback conversion for %s: %f", fromUnit, factor)
        return factor, nil
    }
    
    return 0, fmt.Errorf("no conversion available for unit: %s", fromUnit)
}
```

## Testing Your Implementation

### Unit Tests
```go
func TestOptimizeIngredientForShopping(t *testing.T) {
    ingredient := &GlobalIngredient{
        EstimatedCostValue: 3.99,
        EstimatedCostUnit:  "pound",
        UnitConversions:   `{"cup": 0.125, "pound": 1.0}`,
        PurchaseInfo:      `{"min_purchase_threshold": 2.0}`,
    }
    
    result, err := OptimizeIngredientForShopping(2.0, "cup", ingredient)
    
    assert.NoError(t, err)
    assert.Equal(t, 2.0, result.Quantity)
    assert.Equal(t, "pound", result.Unit)
    assert.Equal(t, 7.98, result.Cost)
}
```

### Integration Tests
```go
func TestAddRecipeToShoppingList(t *testing.T) {
    recipe := &Recipe{
        Ingredients: []RecipeIngredient{
            {IngredientID: "flour-id", Quantity: 2, Unit: "cup"},
            {IngredientID: "honey-id", Quantity: 3, Unit: "tablespoon"},
        },
    }
    
    err := AddRecipeToShoppingList("user-123", recipe)
    assert.NoError(t, err)
    
    // Verify shopping list items were created correctly
    items := GetShoppingListItems("user-123")
    assert.Len(t, items, 2)
    
    // Verify flour optimization
    flourItem := findItem(items, "flour-id")
    assert.Equal(t, 2.0, flourItem.Quantity)
    assert.Equal(t, 7.98, flourItem.Cost)
}
```

## Performance Considerations

### Database Queries
- Batch ingredient lookups: `SELECT * FROM global_ingredients WHERE id IN (?)`
- Use prepared statements for shopping list inserts
- Consider caching frequently accessed ingredient data

### Caching Strategy
```go
type IngredientCache struct {
    cache map[string]*GlobalIngredient
    mutex sync.RWMutex
    ttl   time.Duration
}

func (c *IngredientCache) Get(ingredientID string) (*GlobalIngredient, bool) {
    c.mutex.RLock()
    defer c.mutex.RUnlock()
    
    ingredient, exists := c.cache[ingredientID]
    return ingredient, exists
}
```

## Monitoring & Logging

### Key Metrics to Track
- Ingredient optimization success rate
- Average cost per shopping list
- Unit conversion failure rate
- Performance metrics (response times)

### Logging Examples
```go
log.Printf("Optimized %s: %.2f %s → %.2f %s ($%.2f)", 
    ingredient.Name, 
    recipeQuantity, recipeUnit,
    optimizedQuantity, costUnit,
    totalCost)

log.Printf("Shopping list generated: %d items, total cost: $%.2f", 
    len(items), totalCost)
```

This complete implementation guide ensures your shopping list optimization works correctly with all the enriched ingredient data!