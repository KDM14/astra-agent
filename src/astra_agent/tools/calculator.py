"""Safe mathematical expression calculator tool."""

from __future__ import annotations

import ast
import math
import operator
from typing import Any, Dict
from pydantic import BaseModel, Field

from astra_agent.core.models import PermissionLevel, SideEffectType
from astra_agent.tools.base import BaseTool


class CalculatorInput(BaseModel):
    """Input parameters for calculator."""
    expression: str = Field(..., description="Mathematical expression to evaluate (e.g., '12 * (4.5 + 3.2)')")


class CalculatorTool(BaseTool):
    """Evaluates mathematical expressions safely using AST without arbitrary code execution."""

    name = "calculator"
    description = "Safely evaluates a mathematical expression and returns the numeric result."
    permission_level = PermissionLevel.READ_ONLY
    side_effect_type = SideEffectType.NONE
    idempotent = True
    input_schema = CalculatorInput

    # Allowed operators
    _OPERATORS: Dict[Any, Any] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # Allowed safe functions
    _FUNCTIONS: Dict[str, Any] = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "abs": abs,
        "round": round,
        "ceil": math.ceil,
        "floor": math.floor,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
    }

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant value: {node.value}")

        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            # Prevent excessive exponentiation denial-of-service
            if op_type is ast.Pow and (right > 1000 or (isinstance(left, (int, float)) and abs(left) > 1e6)):
                raise ValueError("Exponentiation values exceed safety limits.")
            return self._OPERATORS[op_type](left, right)

        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in self._OPERATORS:
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
            operand = self._eval_node(node.operand)
            return self._OPERATORS[op_type](operand)

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError(f"Unsupported function call expression: {type(node.func).__name__}")
            if node.func.id in self._FUNCTIONS:
                func = self._FUNCTIONS[node.func.id]
                args = [self._eval_node(a) for a in node.args]
                return func(*args)
            raise ValueError(f"Function call '{node.func.id}' is not allowed.")

        elif isinstance(node, ast.Name):
            if node.id in self._FUNCTIONS:
                return self._FUNCTIONS[node.id]
            raise ValueError(f"Variable or identifier '{node.id}' is not defined.")

        raise ValueError(f"Unsupported expression syntax: {type(node).__name__}")

    def _run(self, inputs: CalculatorInput) -> Dict[str, Any]:
        expr = inputs.expression.strip()
        if not expr:
            raise ValueError("Expression cannot be empty.")
        if len(expr) > 200:
            raise ValueError("Expression exceeds maximum length of 200 characters.")

        parsed = ast.parse(expr, mode="eval")
        result = self._eval_node(parsed.body)
        return {
            "expression": expr,
            "result": result,
            "formatted": str(result),
        }
