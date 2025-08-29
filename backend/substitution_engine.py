import pandas as pd
from typing import Dict, List, Any

class SubstitutionEngine:
    def __init__(self, substitutions_df: pd.DataFrame, ingredients_df: pd.DataFrame):
        self.substitutions_df = substitutions_df
        self.ingredients_df = ingredients_df
        print(f"Substitution Engine initialized with {len(substitutions_df)} substitution rules")
    
    def get_substitutions_for_ingredient(self, ingredient: str, context: str = None) -> List[Dict[str, str]]:
        """Get allowed substitutions for a specific ingredient"""
        ingredient_subs = self.substitutions_df[
            (self.substitutions_df['ingredient'] == ingredient) &
            (self.substitutions_df['allowed'] == True)
        ]
        
        if context:
            context_subs = ingredient_subs[
                ingredient_subs['context'].str.lower().str.contains(context.lower(), na=False)
            ]
            if len(context_subs) == 0:
                context_subs = ingredient_subs
        else:
            context_subs = ingredient_subs
        
        substitution_rules = []
        for _, rule in context_subs.iterrows():
            substitution_rules.append({
                'original': rule['ingredient'],
                'substitute': rule['substitute'],
                'context': rule['context'],
                'rationale': rule['rationale']
            })
        
        return substitution_rules
    
    def get_ingredient_price(self, ingredient: str) -> float:
        """Get base cost per unit for an ingredient"""
        ingredient_info = self.ingredients_df[
            self.ingredients_df['ingredient'] == ingredient
        ]
        if len(ingredient_info) > 0:
            return ingredient_info.iloc[0]['base_cost_per_unit_usd']
        return 0.0
    
    def calculate_cost_impact(self, original_ingredient: str, substitute_ingredient: str) -> str:
        """Calculate cost impact of substitution"""
        original_cost = self.get_ingredient_price(original_ingredient)
        substitute_cost = self.get_ingredient_price(substitute_ingredient)
        
        if original_cost == 0 or substitute_cost == 0:
            return "Cost impact unknown"
        
        cost_diff = substitute_cost - original_cost
        percentage_diff = (cost_diff / original_cost * 100) if original_cost > 0 else 0
        
        if cost_diff > 0:
            return f"${cost_diff:.2f} more expensive ({percentage_diff:.1f}% increase)"
        elif cost_diff < 0:
            return f"${abs(cost_diff):.2f} cheaper ({abs(percentage_diff):.1f}% savings)"
        else:
            return "Same cost"
    
    def check_lead_time_improvement(self, original_ingredient: str, substitute_ingredient: str) -> str:
        """Check lead time difference between ingredients"""
        original_info = self.ingredients_df[
            self.ingredients_df['ingredient'] == original_ingredient
        ]
        substitute_info = self.ingredients_df[
            self.ingredients_df['ingredient'] == substitute_ingredient
        ]
        
        if len(original_info) == 0 or len(substitute_info) == 0:
            return "Lead time comparison unknown"
        
        original_lead_time = original_info.iloc[0]['lead_time_days']
        substitute_lead_time = substitute_info.iloc[0]['lead_time_days']
        
        diff = substitute_lead_time - original_lead_time
        
        if diff < 0:
            return f"{abs(diff)} days faster delivery"
        elif diff > 0:
            return f"{diff} days slower delivery"
        else:
            return "Same lead time"
    
    def find_substitutions(self, impact_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find available substitutions for impacted ingredients"""
        available_substitutions = []
        
        # Handle price shock impacts
        if "affected_dishes" in impact_analysis:
            for dish in impact_analysis["affected_dishes"]:
                if isinstance(dish.get('affected_ingredient'), list):
                    affected_ingredients = dish['affected_ingredient']
                else:
                    affected_ingredients = [dish.get('affected_ingredient')]
                
                for ingredient in affected_ingredients:
                    if not ingredient:
                        continue
                    
                    category = dish.get('category', 'general')
                    substitution_rules = self.get_substitutions_for_ingredient(ingredient, category)
                    
                    for rule in substitution_rules:
                        cost_impact = self.calculate_cost_impact(rule['original'], rule['substitute'])
                        
                        substitution = {
                            'original': rule['original'],
                            'substitute': rule['substitute'],
                            'context': rule['context'],
                            'rationale': rule['rationale'],
                            'cost_impact': cost_impact,
                            'affected_dish': dish['name'],
                            'dish_category': category
                        }
                        
                        available_substitutions.append(substitution)
        
        # Handle supply delay impacts
        elif "at_risk_dishes" in impact_analysis:
            for dish in impact_analysis["at_risk_dishes"]:
                ingredient = dish.get('affected_ingredient')
                if not ingredient:
                    continue
                
                category = dish.get('category', 'general')
                substitution_rules = self.get_substitutions_for_ingredient(ingredient, category)
                
                for rule in substitution_rules:
                    lead_time_improvement = self.check_lead_time_improvement(rule['original'], rule['substitute'])
                    
                    substitution = {
                        'original': rule['original'],
                        'substitute': rule['substitute'],
                        'context': rule['context'],
                        'rationale': rule['rationale'],
                        'lead_time_improvement': lead_time_improvement,
                        'affected_dish': dish['name'],
                        'dish_category': category
                    }
                    
                    available_substitutions.append(substitution)
        
        # Remove duplicates
        seen = set()
        unique_substitutions = []
        
        for sub in available_substitutions:
            key = (sub["original"], sub["substitute"], sub["context"])
            if key not in seen:
                seen.add(key)
                unique_substitutions.append(sub)
        
        return unique_substitutions