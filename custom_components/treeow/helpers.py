def try_read_as_bool(value):
    """Fast boolean conversion with optimized type checking."""
    if value is True or value is False:
        return value
    
    # Use identity comparison for common string values
    if value == 'true':
        return True
    elif value == 'false':
        return False
    elif isinstance(value, str):
        # Only check string case for other string values
        return value.lower() == 'true'
    
    raise ValueError(f'[{value}]无法被转为bool')

def equals_ignore_case(value, target):
    """Fast case-insensitive comparison with early returns."""
    if value is target:
        return True
    
    if type(value) is str and type(target) is str:
        return value.lower() == target.lower()
    
    return value == target

def contains_any_ignore_case(value, targets):
    """Optimized case-insensitive contains check."""
    if not targets:
        return False
    
    # Pre-convert value to lowercase once if it's a string
    if isinstance(value, str):
        value_lower = value.lower()
        for target in targets:
            if isinstance(target, str) and value_lower == target.lower():
                return True
            elif value == target:
                return True
    else:
        # For non-string values, direct comparison
        for target in targets:
            if value == target:
                return True
    
    return False