import splink.comparison_library as cl


def build_name_comparisons_pref_pref() -> list:
    """
    First minimal name-comparison set.

    Current scope:
    - preferred vs preferred only

    The compared column is assumed to be prepared beforehand in the dataframe:
    - preferred_name_norm
    """
    return [
        cl.JaroWinklerAtThresholds(
            "preferred_name_norm",
            score_threshold_or_thresholds=[0.97, 0.92, 0.88],
        )
    ]