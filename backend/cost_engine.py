import pandas as pd
from typing import Dict, List, Any

class CostEngine:
    def __init__(self, ingredients_df: pd.DataFrame, menu_df: pd.DataFrame, menu_bom_df: pd.DataFrame):
        self.ingredients_df = ingredients_df
        self.menu_df = menu_df
        self.menu_bom_df = menu_bom_df
        
        # Business assumptions - matching your previous engine
        self.MONTHLY_SALES_PER_DISH = 100  # Units sold per dish per month
        self.LEAD_TIME_THRESHOLD = 5       # Days threshold for supply risk
        
        print(f"Cost Engine initialized with {len(self.menu_df)} dishes and {len(self.ingredients_df)} ingredients")
    
    def calculate_baseline_costs(self) -> Dict[str, Dict[str, Any]]:
        """Calculate baseline ingredient costs for all menu items"""
        try:
            baseline_costs = {}
            
            for _, menu_item in self.menu_df.iterrows():
                item_name = menu_item['menu_item']
                menu_price = float(menu_item['price_usd'])
                category = menu_item['category']
                
                # Get ingredients for this menu item
                item_ingredients = self.menu_bom_df[
                    self.menu_bom_df['menu_item'] == item_name
                ]
                
                total_ingredient_cost = 0.0
                ingredient_details = {}
                
                for _, bom_row in item_ingredients.iterrows():
                    ingredient = bom_row['ingredient']
                    qty = float(bom_row['qty'])
                    
                    # Get ingredient unit cost
                    ingredient_info = self.ingredients_df[
                        self.ingredients_df['ingredient'] == ingredient
                    ]
                    
                    if len(ingredient_info) > 0:
                        unit_cost = float(ingredient_info.iloc[0]['base_cost_per_unit_usd'])
                        ingredient_cost = qty * unit_cost
                        total_ingredient_cost += ingredient_cost
                        
                        ingredient_details[ingredient] = {
                            'qty': float(qty),
                            'unit_cost': float(unit_cost),
                            'total_cost': float(ingredient_cost),
                            'unit': str(bom_row.get('unit', 'units'))
                        }
                
                baseline_costs[item_name] = {
                    'menu_price': float(menu_price),
                    'ingredient_cost': float(total_ingredient_cost),
                    'cost_percentage': float((total_ingredient_cost / menu_price * 100)) if menu_price > 0 else 0.0,
                    'category': str(category),
                    'ingredients': ingredient_details
                }
            
            return baseline_costs
            
        except Exception as e:
            print(f"Error calculating baseline costs: {e}")
            return {}
    
    def calculate_dish_cost(self, dish_name: str, price_shocks: Dict[str, float] = None) -> Dict[str, Any]:
        """Calculate cost for a single dish with optional price shocks"""
        try:
            baseline_costs = self.calculate_baseline_costs()
            if dish_name not in baseline_costs:
                return None
            
            dish_data = baseline_costs[dish_name]
            cost_breakdown = []
            total_base_cost = dish_data['ingredient_cost']
            total_new_cost = total_base_cost
            
            if price_shocks:
                total_new_cost = 0.0
                for ingredient, data in dish_data['ingredients'].items():
                    base_cost = data['total_cost']
                    shock_pct = price_shocks.get(ingredient, 0)
                    new_cost = base_cost * (1 + shock_pct / 100)
                    total_new_cost += new_cost
                    
                    cost_breakdown.append({
                        'ingredient': str(ingredient),
                        'quantity': float(data['qty']),
                        'unit': str(data['unit']),
                        'base_unit_price': float(data['unit_cost']),
                        'new_unit_price': float(data['unit_cost'] * (1 + shock_pct / 100)),
                        'base_cost': float(base_cost),
                        'new_cost': float(new_cost),
                        'cost_increase': float(new_cost - base_cost),
                        'shock_pct': float(shock_pct)
                    })
            
            return {
                'dish_name': str(dish_name),
                'menu_price': float(dish_data['menu_price']),
                'category': str(dish_data['category']),
                'total_base_cost': float(total_base_cost),
                'total_new_cost': float(total_new_cost),
                'total_cost_increase': float(total_new_cost - total_base_cost),
                'cost_increase_pct': float(((total_new_cost - total_base_cost) / total_base_cost * 100)) if total_base_cost > 0 else 0.0,
                'ingredient_cost_ratio': float(total_base_cost / dish_data['menu_price']) if dish_data['menu_price'] > 0 else 0.0,
                'cost_breakdown': cost_breakdown
            }
            
        except Exception as e:
            print(f"Error calculating cost for {dish_name}: {e}")
            return None
    
    def get_dishes_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get dishes filtered by category with detailed breakdown"""
        try:
            baseline_costs = self.calculate_baseline_costs()
            category_dishes = []
            
            for dish_name, dish_data in baseline_costs.items():
                if dish_data['category'].lower() == category.lower():
                    category_dishes.append({
                        'name': str(dish_name),
                        'category': str(dish_data['category']),
                        'menu_price': float(dish_data['menu_price']),
                        'ingredient_cost': float(dish_data['ingredient_cost']),
                        'cost_percentage': float(dish_data['cost_percentage']),
                        'ingredients': dish_data['ingredients']
                    })
            
            # Sort by cost percentage (highest first)
            category_dishes.sort(key=lambda x: x['cost_percentage'], reverse=True)
            return category_dishes
            
        except Exception as e:
            print(f"Error getting dishes by category: {e}")
            return []
    
    def get_dishes_with_ingredient(self, ingredient: str) -> List[str]:
        """Find all dishes that use a specific ingredient"""
        try:
            dishes_with_ingredient = self.menu_bom_df[
                self.menu_bom_df['ingredient'] == ingredient
            ]['menu_item'].tolist()
            return list(set(dishes_with_ingredient))  # Remove duplicates
        except Exception as e:
            print(f"Error finding dishes with ingredient {ingredient}: {e}")
            return []
    
    def apply_price_shocks(self, price_shocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze impact of price shocks across all dishes"""
        try:
            price_shock_dict = {shock['ingredient']: shock['pct'] for shock in price_shocks}
            
            # Find all affected dishes
            affected_dishes = set()
            for ingredient in price_shock_dict.keys():
                dishes = self.get_dishes_with_ingredient(ingredient)
                affected_dishes.update(dishes)
            
            # Calculate cost impact for each dish
            dish_impacts = []
            total_monthly_impact = 0
            
            for dish_name in affected_dishes:
                dish_analysis = self.calculate_dish_cost(dish_name, price_shock_dict)
                
                if dish_analysis and dish_analysis['total_cost_increase'] > 0:
                    # Calculate monthly impact
                    monthly_cost_increase = (dish_analysis['total_cost_increase'] * 
                                           self.MONTHLY_SALES_PER_DISH)
                    total_monthly_impact += monthly_cost_increase
                    
                    dish_impacts.append({
                        'name': str(dish_analysis['dish_name']),
                        'category': str(dish_analysis['category']),
                        'cost_increase': float(dish_analysis['total_cost_increase']),
                        'percentage_increase': float(dish_analysis['cost_increase_pct']),
                        'monthly_impact': float(monthly_cost_increase),
                        'affected_ingredient': [ing['ingredient'] for ing in dish_analysis['cost_breakdown'] if ing['shock_pct'] > 0],
                        'menu_price': float(dish_analysis['menu_price'])
                    })
            
            # Sort by impact severity
            dish_impacts.sort(key=lambda x: x['monthly_impact'], reverse=True)
            most_impacted = dish_impacts[:5] if dish_impacts else []
            
            return {
                'affected_dishes': dish_impacts,
                'most_impacted_dishes': most_impacted,
                'total_monthly_increase': float(total_monthly_impact),
                'price_shocks_applied': price_shock_dict,
                'total_dishes_affected': int(len(affected_dishes)),
                'assumptions': {
                    'monthly_sales_per_dish': int(self.MONTHLY_SALES_PER_DISH),
                    'calculation_method': 'quantity × unit_price × (1 + shock_pct/100)'
                }
            }
            
        except Exception as e:
            print(f"Error applying price shocks: {e}")
            return {'error': str(e)}
    
    def analyze_supply_delays(self, delays: List[Dict[str, Any]], threshold_days: int) -> Dict[str, Any]:
        """Analyze supply chain delay impacts"""
        try:
            supply_risks = []
            
            for delay in delays:
                ingredient = delay['ingredient']
                extra_days = int(delay['extra_days'])
                
                # Get ingredient info
                ingredient_info = self.ingredients_df[
                    self.ingredients_df['ingredient'] == ingredient
                ]
                
                if len(ingredient_info) == 0:
                    continue
                
                ingredient_data = ingredient_info.iloc[0]
                base_lead_time = int(ingredient_data['lead_time_days'])
                new_lead_time = base_lead_time + extra_days
                
                # Determine risk level
                risk_level = 'LOW'
                if new_lead_time > threshold_days:
                    risk_level = 'HIGH'
                elif extra_days > 2:
                    risk_level = 'MEDIUM'
                
                # Find affected dishes
                affected_dishes = self.get_dishes_with_ingredient(ingredient)
                
                # Get dish categories for affected dishes
                dish_details = []
                for dish_name in affected_dishes:
                    dish_info = self.menu_df[self.menu_df['menu_item'] == dish_name]
                    if len(dish_info) > 0:
                        dish_details.append({
                            'name': str(dish_name),
                            'category': str(dish_info.iloc[0]['category']),
                            'affected_ingredient': str(ingredient),
                            'base_lead_time': int(base_lead_time),
                            'new_lead_time': int(new_lead_time),
                            'extra_days': int(extra_days)
                        })
                
                supply_risks.append({
                    'ingredient': str(ingredient),
                    'base_lead_time_days': int(base_lead_time),
                    'extra_days_delay': int(extra_days),
                    'new_lead_time_days': int(new_lead_time),
                    'risk_level': str(risk_level),
                    'supplier': str(ingredient_data['supplier']),
                    'affected_dishes': [str(dish) for dish in affected_dishes],
                    'affected_dish_count': int(len(affected_dishes))
                })
            
            # Sort by risk level and impact
            risk_priority = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
            supply_risks.sort(key=lambda x: (risk_priority[x['risk_level']], x['affected_dish_count']), reverse=True)
            
            # Create at_risk_dishes format for compatibility
            at_risk_dishes = []
            for risk in supply_risks:
                if risk['risk_level'] in ['HIGH', 'MEDIUM']:
                    for dish_name in risk['affected_dishes']:
                        dish_info = self.menu_df[self.menu_df['menu_item'] == dish_name]
                        if len(dish_info) > 0:
                            at_risk_dishes.append({
                                'name': str(dish_name),
                                'category': str(dish_info.iloc[0]['category']),
                                'affected_ingredient': str(risk['ingredient']),
                                'base_lead_time': int(risk['base_lead_time_days']),
                                'new_lead_time': int(risk['new_lead_time_days']),
                                'extra_days': int(risk['extra_days_delay'])
                            })
            
            return {
                'at_risk_dishes': at_risk_dishes,
                'supply_risks': supply_risks,
                'threshold_days': int(threshold_days),
                'delays_analyzed': {str(delay['ingredient']): int(delay['extra_days']) for delay in delays}
            }
            
        except Exception as e:
            print(f"Error analyzing supply delays: {e}")
            return {'error': str(e)}