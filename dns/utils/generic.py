def list_overlap(lst_1, lst_2):
    return bool(set(lst_1) & set(lst_2))


def dict_key_intersection(dict_1, dict_2):
    return {key: val for key, val in dict_1.items() if key in dict_2.keys()}
