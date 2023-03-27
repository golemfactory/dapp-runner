"""GAOM base module tests."""
from typing import Dict, List, Optional

import pytest
from pydantic import Field

from dapp_runner.descriptor.base import GaomBase, GaomLookupError, GaomRuntimeLookupError


class Level1Descriptor(GaomBase):
    """Test model child."""

    some_attr: str
    runtime_attr: Optional[str] = Field(runtime=True)


class Level0Descriptor(GaomBase):
    """Test model parent."""

    level1: Level1Descriptor
    level1_dict: Dict[str, Level1Descriptor]
    level1_list: List[Level1Descriptor]
    level1_optional: Optional[Level1Descriptor]
    level1_runtime: Optional[Level1Descriptor] = Field(runtime=True)


@pytest.fixture
def example_descriptor() -> Level0Descriptor:
    """Get an example GAOM descriptor fixture."""
    return Level0Descriptor(
        level1=Level1Descriptor(some_attr="some", runtime_attr="run"),
        level1_dict={
            "one": Level1Descriptor(some_attr="some_one", runtime_attr="run_one"),
            "two": Level1Descriptor(some_attr="some_two", runtime_attr="run_two"),
        },
        level1_list=[
            Level1Descriptor(some_attr="some_0", runtime_attr="run_0"),
            Level1Descriptor(some_attr="some_1", runtime_attr="run_1"),
        ],
        level1_optional=Level1Descriptor(some_attr="some_opt", runtime_attr="run_opt"),
        level1_runtime=Level1Descriptor(some_attr="some_run", runtime_attr="run_run"),
    )


@pytest.mark.parametrize(
    "lookup_query, is_runtime, expected_result, expected_error",
    (
        (
            "",
            False,
            {
                "level1": {"some_attr": "some", "runtime_attr": "run"},
                "level1_dict": {
                    "one": {"some_attr": "some_one", "runtime_attr": "run_one"},
                    "two": {"some_attr": "some_two", "runtime_attr": "run_two"},
                },
                "level1_list": [
                    {"some_attr": "some_0", "runtime_attr": "run_0"},
                    {"some_attr": "some_1", "runtime_attr": "run_1"},
                ],
                "level1_optional": {"some_attr": "some_opt", "runtime_attr": "run_opt"},
                "level1_runtime": {"some_attr": "some_run", "runtime_attr": "run_run"},
            },
            None,
        ),
        ("level1", False, {"some_attr": "some", "runtime_attr": "run"}, None),
        (
            "level1.some_attr",
            False,
            "some",
            None,
        ),
        (
            "level1.runtime_attr",
            False,
            None,
            (
                GaomRuntimeLookupError,
                "Fetching a runtime property `runtime_attr` when not in runtime",
            ),
        ),
        (
            "level1.runtime_attr",
            True,
            "run",
            None,
        ),
        (
            "level1_dict.three.some_attr",
            False,
            None,
            (GaomLookupError, "Cannot retrieve `level1_dict.three`"),
        ),
        (
            "level1_dict.two.some_attr",
            False,
            "some_two",
            None,
        ),
        (
            "level1_dict[0].some_attr",
            False,
            "some_two",
            (GaomLookupError, "Cannot retrieve `level1_dict[0]`."),
        ),
        ("level1_list[1].some_attr", False, "some_1", None),
        (
            "level1_list[2].some_attr",
            False,
            None,
            (GaomLookupError, "Cannot retrieve `level1_list[2]`"),
        ),
        (
            "level1_list.one.some_attr",
            False,
            "some_1",
            (GaomLookupError, "Cannot retrieve `level1_list.one`."),
        ),
        ("level1_optional", False, {"some_attr": "some_opt", "runtime_attr": "run_opt"}, None),
        ("level1_optional.some_attr", False, "some_opt", None),
        (
            "level1_optional.runtime_attr",
            False,
            "run_opt",
            (
                GaomRuntimeLookupError,
                "Fetching a runtime property `runtime_attr` when not in runtime",
            ),
        ),
        ("level1_optional.runtime_attr", True, "run_opt", None),
        (
            "level1_optional[1].some_attr",
            False,
            None,
            (GaomLookupError, "Cannot retrieve `level1_optional[1]`"),
        ),
        (
            "level1_runtime",
            False,
            None,
            (
                GaomRuntimeLookupError,
                "Fetching a runtime property `level1_runtime` when not in runtime",
            ),
        ),
        ("level1_runtime.runtime_attr", True, "run_run", None),
    ),
)
def test_lookup(
    example_descriptor, lookup_query, is_runtime, expected_result, expected_error, test_utils
):
    """Test the GaomBase's `lookup`."""

    try:
        result = example_descriptor.lookup(lookup_query, is_runtime)
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
