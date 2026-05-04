from query import _fts5_query, reciprocal_rank_fusion


def test_rrf_scoring():
    # known inputs -> known outputs
    vec_scores = {1: 0.9, 2: 0.8}
    bm25_scores = {2: 1.5, 3: 1.2}

    # rank 0 for doc 1 in vec, rank 1 for doc 2 in vec
    # rank 0 for doc 2 in bm25, rank 1 for doc 3 in bm25

    fused = reciprocal_rank_fusion(vec_scores, bm25_scores, k=3, rrf_k=60)

    # doc 2 should be first since it's in both
    # 2: 1/(60+1+1) + 1/(60+0+1) = 1/62 + 1/61 = 0.0161 + 0.0163 = 0.0325
    # 1: 1/(60+0+1) = 1/61 = 0.0163
    # 3: 1/(60+1+1) = 1/62 = 0.0161
    assert fused[0][0] == 2
    assert fused[1][0] == 1
    assert fused[2][0] == 3


def test_fts5_query_sanitization():
    assert _fts5_query("hello world") == '"hello" "world"'
    assert _fts5_query("special-characters!") == '"special" "characters"'
    assert _fts5_query("") == ""
