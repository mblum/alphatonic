import numpy as np
import pytest
from pandas.testing import assert_frame_equal

from alphatonic.demo import synthetic_market


def test_demo_seed_shapes_and_positive_prices():
    first = synthetic_market(4, 20, seed=71, missing_fraction=0.2)
    second = synthetic_market(4, 20, seed=71, missing_fraction=0.2)
    for a, b in zip(first, second, strict=True):
        assert_frame_equal(a, b)
        assert a.shape == (20, 4)
    assert first[0].index.is_monotonic_increasing
    assert np.all(first[1].to_numpy()[first[1].notna()] > 0)
    assert first[1].isna().any().any()


@pytest.mark.parametrize("key", ["ic", "persistence", "missing_fraction"])
@pytest.mark.parametrize("value", [-0.1, 1, 2])
def test_demo_invalid_parameters_rejected(key, value):
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        synthetic_market(**{key: value})
