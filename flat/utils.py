
#==================================================================================================================================================

def get(container, pred, default=None):
    if isinstance(pred, (int, str)):
        try:
            return container[pred]
        except KeyboardInterrupt:
            raise
        except:
            return default

    elif callable(pred):
        for item in container:
            try:
                is_true = pred(item)
            except KeyboardInterrupt:
                raise
            except:
                continue
            else:
                if is_true:
                    return item
        else:
            return default

    else:
        raise TypeError("Predicate must be eiter an int, a str or a callable.")

def get_either(container, *keys, default=None):
    for key in keys:
        try:
            return container[key]
        except (KeyError, IndexError):
            continue
    else:
        return default
