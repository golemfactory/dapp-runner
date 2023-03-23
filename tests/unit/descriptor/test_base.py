"""GAOM base module tests."""
from typing import Dict, List

import pytest

from dapp_runner.descriptor.base import GaomBase, GaomLookupError


class Level1Descriptor(GaomBase):
    """Test model child."""

    some_attribute: str


class Level0Descriptor(GaomBase):
    """Test model parent."""

    level1: Level1Descriptor
    level1_dict: Dict[str, Level1Descriptor]
    level1_list: List[Level1Descriptor]


@pytest.fixture
def example_descriptor() -> Level0Descriptor:
    """Get an example GAOM descriptor fixture."""
    return Level0Descriptor(
        level1=Level1Descriptor(some_attribute="some"),
        level1_dict={
            "one": Level1Descriptor(some_attribute="some_one"),
            "two": Level1Descriptor(some_attribute="some_two"),
        },
        level1_list=[
            Level1Descriptor(some_attribute="some_0"),
            Level1Descriptor(some_attribute="some_1"),
        ],
    )


@pytest.mark.parametrize(
    "lookup_query, expected_result, expected_error",
    (
        (
            "",
            {
                "level1": {"some_attribute": "some"},
                "level1_dict": {
                    "one": {"some_attribute": "some_one"},
                    "two": {"some_attribute": "some_two"},
                },
                "level1_list": [
                    {"some_attribute": "some_0"},
                    {"some_attribute": "some_1"},
                ],
            },
            None,
        ),
        ("level1", {"some_attribute": "some"}, None),
        (
            "level1.some_attribute",
            "some",
            None,
        ),
        (
            "level1_dict.two.some_attribute",
            "some_two",
            None,
        ),
        (
            "level1_dict[0].some_attribute",
            "some_two",
            (GaomLookupError, "Cannot retrieve `level1_dict[0]`."),
        ),
        ("level1_list[1].some_attribute", "some_1", None),
        (
            "level1_list.one.some_attribute",
            "some_1",
            (GaomLookupError, "Cannot retrieve `level1_list.one`."),
        ),
    ),
)
def test_lookup(example_descriptor, lookup_query, expected_result, expected_error, test_utils):
    """Test the GaomBase's `lookup`."""

    try:
        result = example_descriptor.lookup(lookup_query)
    except Exception as e:
        test_utils.verify_error(expected_error, e)
    else:
        test_utils.verify_error(expected_error, None)

        if isinstance(result, GaomBase):
            result = result.dict()

        assert result == expected_result


@pytest.mark.parametrize(
    "query, expected_components, expected_error",
    (
        (
            "",
            [],
            None,
        ),
        (
            "foo",
            [{"key": "foo", "index": None}],
            None,
        ),
        (
            "foo.bar",
            [{"key": "foo", "index": None}, {"key": "bar", "index": None}],
            None,
        ),
        (
            "foo.bar.baz",
            [
                {"key": "foo", "index": None},
                {"key": "bar", "index": None},
                {"key": "baz", "index": None},
            ],
            None,
        ),
        (
            "foo[2]",
            [{"key": "foo", "index": 2}],
            None,
        ),
        (
            "foo[2].bar",
            [{"key": "foo", "index": 2}, {"key": "bar", "index": None}],
            None,
        ),
        (
            "foo.bar[3]",
            [{"key": "foo", "index": None}, {"key": "bar", "index": 3}],
            None,
        ),
        (
            "foo.bar-baz",
            None,
            (ValueError, "Malformed query"),
        ),
    ),
)
def test_get_lookup_components(query, expected_components, expected_error, test_utils):
    """Test the GaomBase's `_get_lookup_components` method."""

    try:
        components = GaomBase._get_lookup_components(query)
    except Exception as e:
        test_utils.verify_error(expected_error, e)
    else:
        test_utils.verify_error(expected_error, None)
        assert components == expected_components
