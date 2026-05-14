from scripts.search.openalex_utils import reconstruct_abstract, parse_query_blocks


# Tests for reconstruct_abstract

def test_reconstruct_abstract_simple() -> None:
    idx = {"AI": [0], "and": [1], "labor": [2], "markets": [3]}
    assert reconstruct_abstract(idx) == "AI and labor markets"


def test_reconstruct_abstract_repeated_words() -> None:
    idx = {"the": [0, 4], "AI": [1], "affects": [2], "labor": [3]}
    # positions: 0=the, 1=AI, 2=affects, 3=labor, 4=the
    assert reconstruct_abstract(idx) == "the AI affects labor the"


def test_reconstruct_abstract_empty() -> None:
    assert reconstruct_abstract({}) == ""
    assert reconstruct_abstract(None) == ""


def test_reconstruct_abstract_handles_gaps() -> None:
    # Position 2 missing — should still produce a string
    idx = {"a": [0], "c": [3]}
    result = reconstruct_abstract(idx)
    assert "a" in result and "c" in result


# Tests for parse_query_blocks

def test_parse_query_blocks_extracts_three_groups() -> None:
    query = '''
    (
      "artificial intelligence" OR "machine learning"
    )
    AND
    (
      "employment" OR "labor market"
    )
    AND
    (
      "impact" OR "effect"
    )
    '''
    blocks = parse_query_blocks(query)
    assert len(blocks) == 3
    assert "artificial intelligence" in blocks[0]
    assert "machine learning" in blocks[0]
    assert "employment" in blocks[1]
    assert "impact" in blocks[2]


def test_parse_query_blocks_strips_wildcards() -> None:
    query = '("ai") AND ("employment*")'
    blocks = parse_query_blocks(query)
    # wildcards stripped — OpenAlex doesn't use them
    assert blocks[1] == ["employment"]


def test_parse_query_blocks_ignores_comments_and_blank_lines() -> None:
    query = '''
    # English search string
    # Version 1.0

    ("ai") AND ("jobs")
    '''
    blocks = parse_query_blocks(query)
    assert blocks == [["ai"], ["jobs"]]
