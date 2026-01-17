# Backend Integration Guide Creation Prompt

## Context
We've successfully implemented a comprehensive ingredient enrichment system that adds powerful nutrition, costing, and unit conversion capabilities to global ingredients. The system now provides data that enables advanced recipe calculations, kitchen management, and shopping list optimization.

## Your Task
Create a comprehensive integration guide for the frontend team that documents all the new enriched ingredient fields and their applications for building a more powerful ingredient/recipe UX.

## New Enriched Ingredient Fields

### Nutrition Data (per 100g)
- `calories` (decimal)
- `protein` (decimal)  
- `fat` (decimal)
- `carbohydrates` (decimal)
- `sugar` (decimal)

### Spoonacular Integration
- `external_id` (string) - Spoonacular ingredient ID
- `consistency` (string) - "solid", "liquid", etc.
- `possible_units` (string array) - Valid units for this ingredient

### Cost & Shopping Data
- `estimated_cost_value` (decimal) - Cost per unit
- `estimated_cost_unit` (string) - Unit for the cost (e.g., "pound", "cup")
- `purchase_info` (JSON string) - Purchase optimization data
- `unit_conversions` (JSON string) - Conversion factors between units

### Categorization
- `category` (string) - AI-categorized type ("proteins", "dairy", "vegetables", etc.)
- `needs_enrichment` (boolean) - Whether ingredient needs further enrichment

## JSON Field Structures

### `purchase_info` JSON:
```json
{
  "purchase_unit": "pound",
  "purchase_quantity": 1,
  "min_purchase_threshold": 0.5,
  "supplier": "AI Estimate"
}
```

### `unit_conversions` JSON:
```json
{
  "ounce": 0.06,
  "piece": 0.5,
  "oz": 0.06,
  "serving": 0.5,
  "pound": 1.0
}
```

## Frontend Integration Applications

Please document how these fields enable:

### 1. **Smart Recipe Scaling**
- How to use nutrition data to calculate per-serving nutrition facts
- How to use unit conversions to handle different measurement systems
- How to maintain accuracy when users scale recipes up/down

### 2. **Intelligent Shopping Lists**
- How to use `purchase_info` for shopping optimization
- How to convert recipe quantities to store-appropriate purchase units
- How to implement minimum purchase thresholds to reduce waste

### 3. **Recipe Cost Calculation**
- How recipe costs are automatically calculated from ingredient costs
- How to display cost per serving vs total recipe cost
- How to handle cost estimation confidence levels

### 4. **Advanced Unit Conversion**
- How to convert between different measurement units seamlessly
- How to display ingredient quantities in user-preferred units
- How to handle edge cases (liquids vs solids, metric vs imperial)

### 5. **Nutrition Dashboard**
- How to build comprehensive nutrition displays for recipes
- How to calculate daily nutrition values and percentages
- How to handle dietary restrictions and nutritional goals

### 6. **Kitchen Management**
- How to use ingredient categories for pantry organization
- How to implement ingredient substitution suggestions
- How to track ingredient freshness and usage

### 7. **User Experience Enhancements**
- How to provide intelligent ingredient search and filtering
- How to display confidence indicators for AI-generated data
- How to handle missing or incomplete enrichment data gracefully

## Technical Requirements

Please include:

### API Endpoint Documentation
- Which endpoints provide enriched ingredient data
- How to efficiently batch-fetch ingredient information for recipes
- Caching strategies for performance optimization

### Data Validation & Handling
- How to validate JSON field parsing
- Fallback strategies when enrichment data is missing
- Error handling for malformed unit conversion data

### Performance Considerations
- When to preload vs lazy-load enrichment data
- How to optimize nutrition calculations for large recipe collections
- Database query patterns for efficient ingredient lookups

### Real-World Examples
- Code snippets showing how to calculate recipe nutrition
- Examples of unit conversion in different contexts
- Sample shopping list optimization logic

## Sample Integration Scenarios

Please provide detailed implementations for:

1. **Recipe Detail Page**: Displaying complete nutrition facts, cost breakdown, and smart unit conversions
2. **Shopping List Generator**: Converting recipe ingredients to optimized purchase quantities
3. **Recipe Search & Filter**: Using categories and nutrition data for advanced filtering
4. **Meal Planning Dashboard**: Aggregating nutrition and costs across multiple recipes
5. **Kitchen Inventory**: Tracking ingredients with proper categorization and unit handling

## Output Format
Create a comprehensive markdown document that frontend developers can use as a complete reference guide for integrating all enriched ingredient functionality. Include:
- Clear API documentation
- Code examples in JavaScript/TypeScript
- UX/UI considerations
- Performance best practices
- Testing strategies

The guide should enable the frontend team to build a significantly more powerful and user-friendly ingredient/recipe experience leveraging all the enrichment data now available.