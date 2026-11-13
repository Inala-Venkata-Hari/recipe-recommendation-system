"""Conservative product categories; seller overrides take precedence over name rules."""
import re

CATEGORIES=('Recipe ingredient','Ready-made food','Ready-made snack','Utility item')

def product_category(name, override=None):
    if override in CATEGORIES:
        return override
    name=str(name).casefold()
    # Match whole words so biscuit packets are excluded without matching substrings.
    if re.search(r'\b(biscuits?|cookies?|crackers?|chips|crisps|popcorn|candy|candies|chocolate bars?|snack cakes?|pretzels?|cakes?|ice cream|doughnuts?|donuts?|brownies?|muffins?)\b',name):
        return 'Ready-made snack'
    if re.search(r'\b(pizza|sandwich|sandwiches|hamburger|cheeseburger|ready[- ]made|ready[- ]to[- ]eat|frozen meal)\b',name):
        return 'Ready-made food'
    if re.search(r'\b(detergent|dishwashing|soap|shampoo|toothpaste|tissue|foil|garbage bags?)\b',name):
        return 'Utility item'
    return 'Recipe ingredient'


def recipe_cart_codes(codes, categories):
    return [code for code in codes if categories.get(int(code))=='Recipe ingredient']
