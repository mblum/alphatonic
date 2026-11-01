import numpy as np
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype
from pandas.testing import assert_frame_equal


def same_frame(actual, expected):
    assert list(actual) == list(expected)
    # CSV readers normalise text dtypes and datetime resolution across pandas 2/3.
    # Numeric dtypes and UTC timezone remain part of the stored schema.
    if len(expected):
        for name in expected:
            if is_numeric_dtype(expected[name].dtype):
                assert actual[name].dtype == expected[name].dtype, name
            elif is_datetime64_any_dtype(expected[name].dtype):
                assert actual[name].dt.tz == expected[name].dt.tz, name
    assert_frame_equal(
        actual, expected, check_dtype=False, check_exact=False, rtol=2e-13, atol=2e-14
    )


def same_numbers(actual, expected):
    np.testing.assert_array_equal(np.isnan(actual), np.isnan(expected))
    np.testing.assert_allclose(actual, expected, rtol=2e-12, atol=2e-14, equal_nan=True)
