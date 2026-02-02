"""
Unit tests for the _safe_eval_expression function.

Tests the safe AST-based expression evaluator at the function boundary
without mocking any internals.
"""

import pytest

from solace_agent_mesh.workflow.flow_control.conditional import _safe_eval_expression


class TestStringLiterals:
    """Tests for string literal evaluation."""

    def test_single_quoted_string(self):
        assert _safe_eval_expression("'hello'") == "hello"

    def test_double_quoted_string(self):
        assert _safe_eval_expression('"world"') == "world"

    def test_empty_string(self):
        assert _safe_eval_expression("''") == ""

    def test_string_with_spaces(self):
        assert _safe_eval_expression("'hello world'") == "hello world"

    def test_string_with_special_characters(self):
        assert _safe_eval_expression("'hello\\nworld'") == "hello\nworld"


class TestNumericLiterals:
    """Tests for numeric literal evaluation."""

    def test_positive_integer(self):
        assert _safe_eval_expression("42") == 42

    def test_negative_integer(self):
        assert _safe_eval_expression("-42") == -42

    def test_zero(self):
        assert _safe_eval_expression("0") == 0

    def test_positive_float(self):
        assert _safe_eval_expression("3.14") == 3.14

    def test_negative_float(self):
        assert _safe_eval_expression("-3.14") == -3.14

    def test_scientific_notation(self):
        assert _safe_eval_expression("1e10") == 1e10

    def test_unary_plus(self):
        assert _safe_eval_expression("+5") == 5


class TestBooleanLiterals:
    """Tests for boolean literal evaluation."""

    def test_true_lowercase(self):
        assert _safe_eval_expression("true") is True

    def test_false_lowercase(self):
        assert _safe_eval_expression("false") is False

    def test_true_python_style(self):
        assert _safe_eval_expression("True") is True

    def test_false_python_style(self):
        assert _safe_eval_expression("False") is False

    def test_true_mixed_case(self):
        assert _safe_eval_expression("TRUE") is True

    def test_false_mixed_case(self):
        assert _safe_eval_expression("FALSE") is False


class TestNullLiterals:
    """Tests for null/None literal evaluation."""

    def test_null_lowercase(self):
        assert _safe_eval_expression("null") is None

    def test_none_lowercase(self):
        assert _safe_eval_expression("none") is None

    def test_none_python_style(self):
        assert _safe_eval_expression("None") is None

    def test_null_mixed_case(self):
        assert _safe_eval_expression("NULL") is None


class TestEqualityComparisons:
    """Tests for equality comparison operators."""

    def test_string_equality_true(self):
        assert _safe_eval_expression("'foo' == 'foo'") is True

    def test_string_equality_false(self):
        assert _safe_eval_expression("'foo' == 'bar'") is False

    def test_string_inequality_true(self):
        assert _safe_eval_expression("'foo' != 'bar'") is True

    def test_string_inequality_false(self):
        assert _safe_eval_expression("'foo' != 'foo'") is False

    def test_integer_equality(self):
        assert _safe_eval_expression("42 == 42") is True

    def test_integer_inequality(self):
        assert _safe_eval_expression("42 != 43") is True

    def test_float_equality(self):
        assert _safe_eval_expression("3.14 == 3.14") is True

    def test_boolean_equality(self):
        assert _safe_eval_expression("true == true") is True

    def test_boolean_inequality(self):
        assert _safe_eval_expression("true != false") is True

    def test_null_equality(self):
        assert _safe_eval_expression("null == null") is True

    def test_mixed_type_equality(self):
        # Python allows comparing different types
        assert _safe_eval_expression("'42' == 42") is False


class TestNumericComparisons:
    """Tests for numeric comparison operators."""

    def test_greater_than_true(self):
        assert _safe_eval_expression("10 > 5") is True

    def test_greater_than_false(self):
        assert _safe_eval_expression("5 > 10") is False

    def test_greater_than_equal(self):
        assert _safe_eval_expression("5 > 5") is False

    def test_less_than_true(self):
        assert _safe_eval_expression("5 < 10") is True

    def test_less_than_false(self):
        assert _safe_eval_expression("10 < 5") is False

    def test_less_than_equal(self):
        assert _safe_eval_expression("5 < 5") is False

    def test_greater_than_or_equal_greater(self):
        assert _safe_eval_expression("10 >= 5") is True

    def test_greater_than_or_equal_equal(self):
        assert _safe_eval_expression("5 >= 5") is True

    def test_greater_than_or_equal_less(self):
        assert _safe_eval_expression("5 >= 10") is False

    def test_less_than_or_equal_less(self):
        assert _safe_eval_expression("5 <= 10") is True

    def test_less_than_or_equal_equal(self):
        assert _safe_eval_expression("5 <= 5") is True

    def test_less_than_or_equal_greater(self):
        assert _safe_eval_expression("10 <= 5") is False

    def test_float_comparisons(self):
        assert _safe_eval_expression("3.14 > 3.0") is True
        assert _safe_eval_expression("2.5 < 3.0") is True

    def test_negative_number_comparisons(self):
        assert _safe_eval_expression("-5 < 0") is True
        assert _safe_eval_expression("-10 < -5") is True


class TestChainedComparisons:
    """Tests for chained comparison operators (e.g., 1 < x < 10)."""

    def test_chained_less_than_true(self):
        assert _safe_eval_expression("1 < 5 < 10") is True

    def test_chained_less_than_false_first(self):
        assert _safe_eval_expression("5 < 1 < 10") is False

    def test_chained_less_than_false_second(self):
        assert _safe_eval_expression("1 < 10 < 5") is False

    def test_chained_less_equal_true(self):
        assert _safe_eval_expression("1 <= 5 <= 10") is True

    def test_chained_with_equal_values(self):
        assert _safe_eval_expression("5 <= 5 <= 5") is True

    def test_chained_greater_than(self):
        assert _safe_eval_expression("10 > 5 > 1") is True


class TestContainmentOperators:
    """Tests for 'in' and 'not in' operators."""

    def test_string_in_string_true(self):
        assert _safe_eval_expression("'foo' in 'foobar'") is True

    def test_string_in_string_false(self):
        assert _safe_eval_expression("'baz' in 'foobar'") is False

    def test_string_not_in_string_true(self):
        assert _safe_eval_expression("'baz' not in 'foobar'") is True

    def test_string_not_in_string_false(self):
        assert _safe_eval_expression("'foo' not in 'foobar'") is False

    def test_empty_string_in_string(self):
        assert _safe_eval_expression("'' in 'foobar'") is True

    def test_case_sensitive_containment(self):
        assert _safe_eval_expression("'FOO' in 'foobar'") is False


class TestBooleanAndOperator:
    """Tests for the 'and' boolean operator."""

    def test_and_both_true(self):
        assert _safe_eval_expression("true and true") is True

    def test_and_first_false(self):
        assert _safe_eval_expression("false and true") is False

    def test_and_second_false(self):
        assert _safe_eval_expression("true and false") is False

    def test_and_both_false(self):
        assert _safe_eval_expression("false and false") is False

    def test_and_with_comparisons(self):
        assert _safe_eval_expression("5 > 3 and 10 > 5") is True

    def test_and_with_mixed_comparisons(self):
        assert _safe_eval_expression("5 > 3 and 10 < 5") is False

    def test_and_multiple_operands(self):
        assert _safe_eval_expression("true and true and true") is True

    def test_and_multiple_operands_one_false(self):
        assert _safe_eval_expression("true and false and true") is False


class TestBooleanOrOperator:
    """Tests for the 'or' boolean operator."""

    def test_or_both_true(self):
        assert _safe_eval_expression("true or true") is True

    def test_or_first_true(self):
        assert _safe_eval_expression("true or false") is True

    def test_or_second_true(self):
        assert _safe_eval_expression("false or true") is True

    def test_or_both_false(self):
        assert _safe_eval_expression("false or false") is False

    def test_or_with_comparisons(self):
        assert _safe_eval_expression("5 < 3 or 10 > 5") is True

    def test_or_multiple_operands(self):
        assert _safe_eval_expression("false or false or true") is True

    def test_or_multiple_operands_all_false(self):
        assert _safe_eval_expression("false or false or false") is False


class TestBooleanNotOperator:
    """Tests for the 'not' boolean operator."""

    def test_not_true(self):
        assert _safe_eval_expression("not true") is False

    def test_not_false(self):
        assert _safe_eval_expression("not false") is True

    def test_not_comparison(self):
        assert _safe_eval_expression("not 5 > 10") is True

    def test_not_not(self):
        assert _safe_eval_expression("not not true") is True

    def test_not_with_parentheses(self):
        assert _safe_eval_expression("not (5 < 3)") is True


class TestComplexBooleanExpressions:
    """Tests for complex boolean expressions combining and/or/not."""

    def test_and_or_precedence(self):
        # 'and' has higher precedence than 'or'
        # true or false and false => true or (false and false) => true
        assert _safe_eval_expression("true or false and false") is True

    def test_or_and_precedence(self):
        # false and true or true => (false and true) or true => true
        assert _safe_eval_expression("false and true or true") is True

    def test_parentheses_override_precedence(self):
        # (true or false) and false => true and false => false
        assert _safe_eval_expression("(true or false) and false") is False

    def test_not_and_combination(self):
        assert _safe_eval_expression("not false and true") is True

    def test_not_or_combination(self):
        assert _safe_eval_expression("not true or true") is True

    def test_complex_expression_with_comparisons(self):
        assert _safe_eval_expression("5 > 3 and (10 < 5 or 20 > 15)") is True

    def test_nested_parentheses(self):
        assert _safe_eval_expression("((true and true) or false) and true") is True


class TestParentheses:
    """Tests for parentheses grouping."""

    def test_simple_parentheses(self):
        assert _safe_eval_expression("(true)") is True

    def test_nested_parentheses(self):
        assert _safe_eval_expression("((true))") is True

    def test_parentheses_with_comparison(self):
        assert _safe_eval_expression("(5 > 3)") is True

    def test_parentheses_change_result(self):
        # Without parentheses: false and true or true => false or true => true
        # With parentheses: false and (true or true) => false and true => false
        assert _safe_eval_expression("false and (true or true)") is False


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_whitespace_handling(self):
        # Note: Leading whitespace causes IndentationError in Python AST
        # Internal whitespace is fine
        assert _safe_eval_expression("5  >  3") is True

    def test_string_with_numbers(self):
        assert _safe_eval_expression("'123' == '123'") is True

    def test_empty_string_equality(self):
        assert _safe_eval_expression("'' == ''") is True

    def test_very_large_number(self):
        assert _safe_eval_expression("999999999999999999 > 0") is True

    def test_very_small_float(self):
        assert _safe_eval_expression("0.0000001 > 0") is True

    def test_zero_comparisons(self):
        assert _safe_eval_expression("0 == 0") is True
        assert _safe_eval_expression("0 > -1") is True
        assert _safe_eval_expression("0 < 1") is True


class TestInvalidExpressions:
    """Tests for invalid expressions that should raise ValueError."""

    def test_unknown_identifier(self):
        with pytest.raises(ValueError, match="Unknown identifier"):
            _safe_eval_expression("unknown_var")

    def test_undefined_variable(self):
        with pytest.raises(ValueError, match="Unknown identifier"):
            _safe_eval_expression("x == 5")

    def test_invalid_syntax_missing_operand(self):
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            _safe_eval_expression("5 >")

    def test_invalid_syntax_double_operator(self):
        # Note: >> is a valid right-shift operator (BinOp) in Python,
        # so it's parsed successfully but rejected as unsupported
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 >> 3")

    def test_invalid_syntax_unclosed_string(self):
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            _safe_eval_expression("'unclosed")

    def test_invalid_syntax_unclosed_parenthesis(self):
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            _safe_eval_expression("(5 > 3")

    def test_invalid_syntax_empty_expression(self):
        with pytest.raises(ValueError, match="Invalid expression syntax"):
            _safe_eval_expression("")


class TestUnsupportedExpressions:
    """Tests for unsupported but syntactically valid expressions."""

    def test_arithmetic_addition(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 + 3")

    def test_arithmetic_subtraction(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 - 3")

    def test_arithmetic_multiplication(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 * 3")

    def test_arithmetic_division(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 / 3")

    def test_function_call(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("len('hello')")

    def test_method_call(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("'hello'.upper()")

    def test_list_literal(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("[1, 2, 3]")

    def test_dict_literal(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("{'a': 1}")

    def test_attribute_access(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("foo.bar")

    def test_subscript_access(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("'hello'[0]")

    def test_lambda(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("lambda x: x")

    def test_comprehension(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("[x for x in [1,2,3]]")

    def test_ternary_expression(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("1 if true else 0")

    def test_bitwise_and(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 & 3")

    def test_bitwise_or(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 | 3")

    def test_power_operator(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("2 ** 3")

    def test_modulo_operator(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 % 3")

    def test_floor_division(self):
        with pytest.raises(ValueError, match="Unsupported expression type"):
            _safe_eval_expression("5 // 3")


class TestUnsupportedOperators:
    """Tests for operators that are syntactically valid but not supported."""

    def test_is_comparison_blocked(self):
        # 'is' comparison operator is not supported
        with pytest.raises(ValueError, match="Unsupported comparison operator"):
            _safe_eval_expression("None is None")

    def test_is_not_comparison_blocked(self):
        # 'is not' comparison operator is not supported
        with pytest.raises(ValueError, match="Unsupported comparison operator"):
            _safe_eval_expression("1 is not None")

    def test_bitwise_not_blocked(self):
        # Bitwise NOT (~) is a unary operator that's not supported
        with pytest.raises(ValueError, match="Unsupported unary operator"):
            _safe_eval_expression("~5")


class TestSecurityCases:
    """Tests to ensure dangerous operations are blocked."""

    # Function call attacks
    def test_import_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__import__('os')")

    def test_exec_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("exec('print(1)')")

    def test_eval_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("eval('1+1')")

    def test_open_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("open('/etc/passwd')")

    def test_globals_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("globals()")

    def test_locals_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("locals()")

    def test_compile_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("compile('x=1', '', 'exec')")

    def test_getattr_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("getattr('', '__class__')")

    def test_setattr_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("setattr(x, 'y', 1)")

    def test_delattr_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("delattr(x, 'y')")

    def test_dir_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("dir()")

    def test_vars_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("vars()")

    def test_input_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("input('prompt')")

    def test_print_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("print('hello')")

    def test_type_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("type('X', (), {})")

    # Attribute access attacks
    def test_dunder_class_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("''.__class__")

    def test_dunder_bases_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("''.__class__.__bases__")

    def test_dunder_mro_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("''.__class__.__mro__")

    def test_dunder_subclasses_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("''.__class__.__subclasses__()")

    def test_dunder_globals_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("(lambda: 0).__globals__")

    def test_dunder_code_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("(lambda: 0).__code__")

    def test_dunder_builtins_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__builtins__")

    def test_dunder_import_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__import__")

    # Object introspection attacks
    def test_class_from_string(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("''.__class__.__bases__[0].__subclasses__()")

    def test_breakout_via_mro(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("().__class__.__mro__[1].__subclasses__()")

    # Code execution via os/subprocess
    def test_os_system_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__import__('os').system('ls')")

    def test_subprocess_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__import__('subprocess').call(['ls'])")

    # File system access
    def test_file_read_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("open('/etc/passwd').read()")

    def test_pathlib_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__import__('pathlib').Path('/etc/passwd').read_text()")

    # Network access
    def test_socket_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__import__('socket').socket()")

    def test_urllib_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("__import__('urllib.request').urlopen('http://evil.com')")

    # Lambda and code object manipulation
    def test_lambda_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("lambda: __import__('os')")

    def test_nested_lambda_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("(lambda: lambda: 1)()")

    # Generator expressions
    def test_generator_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("(x for x in [1,2,3])")

    def test_generator_with_import_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("list(x for x in __import__('os').listdir('.'))")

    # Walrus operator (Python 3.8+)
    def test_walrus_operator_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("(x := 1)")

    # F-string code execution (these parse as JoinedStr)
    def test_fstring_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("f'{__import__(\"os\")}'")

    # Slice manipulation
    def test_slice_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("'hello'[0:2]")

    # Star expressions
    def test_starred_blocked(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("[*[1,2,3]]")

    # Augmented assignment (though not valid in eval mode)
    def test_augmented_assign_syntax_error(self):
        with pytest.raises(ValueError):
            _safe_eval_expression("x += 1")


class TestRealWorldExpressions:
    """Tests for expressions similar to those used in actual workflows."""

    def test_status_check(self):
        assert _safe_eval_expression("'success' == 'success'") is True

    def test_numeric_threshold(self):
        assert _safe_eval_expression("500 > 100") is True

    def test_boolean_flag_check(self):
        assert _safe_eval_expression("true == true") is True

    def test_string_contains_error(self):
        assert _safe_eval_expression("'Error' in 'Error: something went wrong'") is True

    def test_multiple_conditions(self):
        assert _safe_eval_expression("'active' == 'active' and 10 > 5") is True

    def test_fallback_condition(self):
        assert _safe_eval_expression("'failed' == 'success' or 'failed' == 'failed'") is True

    def test_not_empty_check(self):
        assert _safe_eval_expression("'some value' != ''") is True

    def test_null_check(self):
        assert _safe_eval_expression("null == null") is True

    def test_not_null_check(self):
        # This would be checking if a resolved value is not None
        assert _safe_eval_expression("'value' != None") is True
