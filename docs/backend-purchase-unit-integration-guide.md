# Backend Integration Guide: Purchase Unit Conversions

## 🎯 **What This Enables for the Backend Team**

Now that ingredients have complete purchase unit conversion mappings, the backend can implement **intelligent inventory management** and **shopping optimization**. Here's the complete workflow:

---

## 🏪 **1. Inventory Management with Unit Conversions**

### **The Problem Solved:**
- User buys "1 bag peas" (physical purchase)
- Recipe requires "50 grams peas" (recipe unit)
- System needs to track: *"Do I have enough peas for this recipe?"*

### **Backend Implementation:**

```json
{
  "ingredient_id": "d2kdlqppeops73cbudl0",
  "name": "snap pea",
  "inventory": {
    "purchase_items": [
      {
        "purchase_unit": "bag",
        "quantity_purchased": 1.0,
        "quantity_remaining": 0.8,
        "purchase_date": "2025-01-15",
        "expiry_date": "2025-01-22"
      }
    ],
    "total_available_in_recipe_units": {
      "pea pod": 80.0,    // 0.8 bags × 100 pea pods/bag
      "g": 240.0,         // Convert via Spoonacular if needed
      "cup": 2.0          // Convert via Spoonacular if needed
    }
  }
}
```

### **API Endpoints Needed:**

```typescript
// Add purchased items to inventory
POST /api/inventory/add
{
  "ingredient_id": "d2kdlqppeops73cbudl0",
  "purchase_unit": "bag", 
  "quantity": 1.0,
  "cost": 3.99,
  "purchase_date": "2025-01-15"
}

// Check recipe feasibility
POST /api/inventory/check-recipe
{
  "recipe_ingredients": [
    {
      "ingredient_id": "d2kdlqppeops73cbudl0",
      "required_amount": 50,
      "required_unit": "g"
    }
  ]
}
// Returns: { "feasible": true, "missing_ingredients": [] }
```

---

## 🧮 **2. Unit Conversion Logic**

### **Backend Conversion Engine:**

```python
def convert_units(ingredient_id: str, amount: float, from_unit: str, to_unit: str) -> float:
    """Convert between any units using the conversion mappings"""
    
    # Get ingredient conversion data
    ingredient = get_ingredient(ingredient_id)
    conversions = ingredient.unit_conversions  # From our fix!
    cost_unit = ingredient.estimated_cost_unit
    
    # Convert from_unit → cost_unit → to_unit
    amount_in_cost_unit = amount * conversions[from_unit]  
    converted_amount = amount_in_cost_unit / conversions[to_unit]
    
    return converted_amount

# Example: Convert 1 bag peas → grams
convert_units("d2kdlqppeops73cbudl0", 1.0, "bag", "g")
# Returns: 300.0 (if 1 bag = 100 pea pods, 1 pea pod = 3g via Spoonacular)
```

### **Inventory Deduction Logic:**

```python
def consume_ingredient(ingredient_id: str, amount: float, unit: str):
    """Consume ingredient from inventory, tracking across purchase units"""
    
    # Convert to cost unit for tracking
    cost_unit = get_ingredient(ingredient_id).estimated_cost_unit
    amount_in_cost_unit = convert_units(ingredient_id, amount, unit, cost_unit)
    
    # Deduct from purchase items (FIFO - oldest first)
    for purchase_item in inventory.purchase_items.order_by('purchase_date'):
        if purchase_item.quantity_remaining <= 0:
            continue
            
        # Convert purchase quantity to cost unit
        available_in_cost_unit = convert_units(
            ingredient_id, 
            purchase_item.quantity_remaining,
            purchase_item.purchase_unit, 
            cost_unit
        )
        
        if available_in_cost_unit >= amount_in_cost_unit:
            # Consume from this purchase
            consumed_in_purchase_unit = convert_units(
                ingredient_id, amount_in_cost_unit, cost_unit, purchase_item.purchase_unit
            )
            purchase_item.quantity_remaining -= consumed_in_purchase_unit
            break
        else:
            # Consume entire purchase and continue to next
            amount_in_cost_unit -= available_in_cost_unit
            purchase_item.quantity_remaining = 0.0

# Example: Recipe uses 50g peas
consume_ingredient("d2kdlqppeops73cbudl0", 50, "g")
# Automatically deducts from "bag" inventory
```

---

## 🚨 **3. Smart Alerting System**

### **Low Stock Alerts:**

```python
def check_low_stock_alerts(user_id: str) -> List[Alert]:
    """Generate alerts for low stock based on purchase thresholds"""
    alerts = []
    
    for ingredient in user_inventory:
        # Calculate total available in cost unit
        total_available = sum([
            convert_units(ingredient.id, item.quantity_remaining, item.purchase_unit, ingredient.estimated_cost_unit)
            for item in ingredient.purchase_items
        ])
        
        # Check against minimum purchase threshold
        if total_available < ingredient.min_purchase_threshold:
            alerts.append({
                "type": "LOW_STOCK",
                "ingredient_name": ingredient.name,
                "current_amount": total_available,
                "current_unit": ingredient.estimated_cost_unit,
                "threshold": ingredient.min_purchase_threshold,
                "suggested_purchase": {
                    "unit": ingredient.purchase_unit,
                    "quantity": 1,  # Based on purchase_quantity
                    "estimated_cost": ingredient.estimated_cost_per_unit * ingredient.purchase_quantity
                }
            })
    
    return alerts

# Example Alert Response:
{
  "type": "LOW_STOCK",
  "ingredient_name": "snap pea",
  "current_amount": 8.0,
  "current_unit": "pea pod", 
  "threshold": 25.0,
  "suggested_purchase": {
    "unit": "bag",
    "quantity": 1,
    "estimated_cost": 3.99
  }
}
```

### **Recipe Planning Alerts:**

```python
def plan_weekly_recipes(user_id: str, selected_recipes: List[str]) -> Dict:
    """Check if user has enough inventory for planned recipes"""
    
    # Aggregate all ingredient needs
    total_needs = {}
    for recipe_id in selected_recipes:
        recipe = get_recipe(recipe_id)
        for ingredient in recipe.ingredients:
            if ingredient.ingredient_id in total_needs:
                # Convert to common unit and add
                existing_amount = total_needs[ingredient.ingredient_id]['amount']
                existing_unit = total_needs[ingredient.ingredient_id]['unit']
                
                # Convert both to cost unit and add
                cost_unit = get_ingredient(ingredient.ingredient_id).estimated_cost_unit
                existing_in_cost = convert_units(ingredient.ingredient_id, existing_amount, existing_unit, cost_unit)
                new_in_cost = convert_units(ingredient.ingredient_id, ingredient.quantity, ingredient.unit, cost_unit)
                
                total_needs[ingredient.ingredient_id] = {
                    'amount': existing_in_cost + new_in_cost,
                    'unit': cost_unit
                }
            else:
                total_needs[ingredient.ingredient_id] = {
                    'amount': ingredient.quantity,
                    'unit': ingredient.unit
                }
    
    # Check availability and generate shopping list
    shopping_list = []
    for ingredient_id, needed in total_needs.items():
        available = get_available_amount(ingredient_id, needed['unit'])
        
        if available < needed['amount']:
            shortage = needed['amount'] - available
            ingredient = get_ingredient(ingredient_id)
            
            # Calculate purchase units needed
            purchase_units_needed = math.ceil(
                convert_units(ingredient_id, shortage, needed['unit'], ingredient.purchase_unit)
            )
            
            shopping_list.append({
                "ingredient_id": ingredient_id,
                "ingredient_name": ingredient.name,
                "needed_amount": shortage,
                "needed_unit": needed['unit'],
                "purchase_suggestion": {
                    "unit": ingredient.purchase_unit,
                    "quantity": purchase_units_needed,
                    "estimated_cost": purchase_units_needed * ingredient.estimated_cost_per_unit * ingredient.purchase_quantity
                }
            })
    
    return {
        "recipes_feasible": len(shopping_list) == 0,
        "shopping_list": shopping_list,
        "total_estimated_cost": sum([item['purchase_suggestion']['estimated_cost'] for item in shopping_list])
    }
```

---

## 🛒 **4. Shopping List Optimization**

### **Smart Purchase Suggestions:**

```python
def optimize_shopping_list(ingredient_shortages: List[Dict]) -> List[Dict]:
    """Optimize purchase quantities to minimize waste and cost"""
    
    optimized_list = []
    
    for shortage in ingredient_shortages:
        ingredient = get_ingredient(shortage['ingredient_id'])
        needed_amount = shortage['needed_amount']
        needed_unit = shortage['needed_unit']
        
        # Convert to purchase units
        needed_in_purchase_units = convert_units(
            ingredient.id, needed_amount, needed_unit, ingredient.purchase_unit
        )
        
        # Apply minimum purchase threshold
        min_purchase = ingredient.min_purchase_threshold
        min_purchase_in_purchase_units = convert_units(
            ingredient.id, min_purchase, ingredient.estimated_cost_unit, ingredient.purchase_unit
        )
        
        # Purchase the larger of: needed amount or minimum threshold
        purchase_quantity = max(needed_in_purchase_units, min_purchase_in_purchase_units)
        
        # Round up to whole purchase units
        purchase_quantity = math.ceil(purchase_quantity)
        
        optimized_list.append({
            "ingredient_id": ingredient.id,
            "ingredient_name": ingredient.name,
            "purchase_unit": ingredient.purchase_unit,
            "purchase_quantity": purchase_quantity,
            "estimated_cost": purchase_quantity * ingredient.estimated_cost_per_unit * ingredient.purchase_quantity,
            "will_satisfy_recipes": True,
            "leftover_amount": convert_units(
                ingredient.id, 
                purchase_quantity - needed_in_purchase_units, 
                ingredient.purchase_unit, 
                needed_unit
            ),
            "leftover_unit": needed_unit
        })
    
    return optimized_list

# Example Optimized Shopping List:
{
  "ingredient_name": "snap pea",
  "purchase_unit": "bag",
  "purchase_quantity": 1,
  "estimated_cost": 3.99,
  "will_satisfy_recipes": true,
  "leftover_amount": 150.0,
  "leftover_unit": "g"
}
```

---

## 📱 **5. Mobile App Integration**

### **Inventory Management Screen:**
```json
// GET /api/inventory/summary
{
  "inventory_items": [
    {
      "ingredient_name": "snap pea",
      "purchase_display": "0.8 bags remaining",
      "recipe_units_available": [
        { "unit": "pea pod", "amount": 80 },
        { "unit": "g", "amount": 240 },
        { "unit": "cup", "amount": 2.0 }
      ],
      "expires_in_days": 5,
      "low_stock": false
    }
  ]
}
```

### **Recipe Feasibility Check:**
```json
// POST /api/recipes/check-feasibility
{
  "recipe_id": "abc123",
  "response": {
    "can_make": true,
    "ingredient_status": [
      {
        "ingredient_name": "snap pea", 
        "required": "50g",
        "available": "240g",
        "sufficient": true
      }
    ],
    "estimated_cost": 0.83  // Cost of ingredients used
  }
}
```

---

## 🎯 **6. Implementation Priority**

### **Phase 1: Core Conversion Engine**
1. ✅ Unit conversion utility functions
2. ✅ Inventory tracking with purchase units
3. ✅ Basic deduction logic

### **Phase 2: Smart Features**  
1. 🔲 Low stock alerts
2. 🔲 Recipe feasibility checking
3. 🔲 Shopping list optimization

### **Phase 3: Advanced Features**
1. 🔲 Weekly meal planning
2. 🔲 Cost tracking and budgeting  
3. 🔲 Expiry date management
4. 🔲 Waste reduction suggestions

---

## 🔧 **Database Schema Updates Needed**

```sql
-- Inventory tracking table
CREATE TABLE user_ingredient_inventory (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    ingredient_id UUID REFERENCES global_ingredients(id),
    purchase_unit VARCHAR(50),
    quantity_purchased DECIMAL(10,3),
    quantity_remaining DECIMAL(10,3),
    cost_paid DECIMAL(10,2),
    purchase_date DATE,
    expiry_date DATE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Low stock alerts
CREATE TABLE inventory_alerts (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    ingredient_id UUID REFERENCES global_ingredients(id),
    alert_type VARCHAR(50), -- 'LOW_STOCK', 'EXPIRED', 'RECIPE_SHORTAGE'
    triggered_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    alert_data JSONB
);
```

---

## 🎉 **Bottom Line**

With purchase unit conversions fixed, the backend team can now build:

- **🏠 Smart Pantry Management**: "I have 0.8 bags of peas = 240g available"
- **🍳 Intelligent Recipe Planning**: "This recipe needs 50g peas - you have enough!"  
- **🛒 Optimized Shopping Lists**: "Buy 1 bag peas ($3.99) - will satisfy 3 recipes"
- **🚨 Proactive Alerts**: "Low on peas (8 remaining, threshold 25) - suggest buying 1 bag"
- **💰 Cost Tracking**: "This week's meals will cost $47.83 in ingredients"

The foundation is now solid for building a **comprehensive kitchen management system**!