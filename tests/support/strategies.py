from hypothesis import strategies as st

finite_or_missing = st.one_of(st.integers(-20, 20).map(float), st.just(float("nan")))
paired_vectors = st.lists(st.tuples(finite_or_missing, finite_or_missing), min_size=1, max_size=40)
