def try_read_as_bool(value):
    if value is True or value is False:
        return value

    if isinstance(value, str):
        return value.lower() == 'true'

    raise ValueError(f'[{value}] cannot be converted to bool')
