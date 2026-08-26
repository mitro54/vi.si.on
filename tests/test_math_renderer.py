"""
Unit tests for LaTeX math and markdown rendering engine.
"""

from desktop_ambient_ai.ui.math_renderer import MathParser, render_markdown_with_math
from desktop_ambient_ai.vision.spatial_finder import ThemeConfig


def test_basic_math_symbols():

    # Greek letters
    assert "α" in MathParser.parse_math_to_html(r"\alpha")
    assert "θ" in MathParser.parse_math_to_html(r"\theta")
    assert "Ω" in MathParser.parse_math_to_html(r"\Omega")
    assert "π" in MathParser.parse_math_to_html(r"\pi")

    # Blackboard bold
    assert "ℝ" in MathParser.parse_math_to_html(r"\mathbb{R}")
    assert "ℂ" in MathParser.parse_math_to_html(r"\mathbb{C}")
    assert "ℤ" in MathParser.parse_math_to_html(r"\mathbb{Z}")

    # Operators
    assert "·" in MathParser.parse_math_to_html(r"\cdot")
    assert "×" in MathParser.parse_math_to_html(r"\times")
    assert "≤" in MathParser.parse_math_to_html(r"\leq")
    assert "≥" in MathParser.parse_math_to_html(r"\geq")
    assert "≠" in MathParser.parse_math_to_html(r"\neq")
    assert "≈" in MathParser.parse_math_to_html(r"\approx")
    assert "⇔" in MathParser.parse_math_to_html(r"\Leftrightarrow")
    assert "⟺" in MathParser.parse_math_to_html(r"\Longleftrightarrow")


def test_vectors_and_accents():
    # Vector accents
    vec_html = MathParser.parse_math_to_html(r"\vec{v}")
    assert "math-vector" in vec_html
    assert "&#x20D7;" in vec_html

    # Standard unit basis vectors
    hat_i = MathParser.parse_math_to_html(r"\hat{\imath}")
    assert "&#x0131;&#x0302;" in hat_i or "i&#x0302;" in hat_i

    hat_j = MathParser.parse_math_to_html(r"\hat{\jmath}")
    assert "&#x0237;&#x0302;" in hat_j or "j&#x0302;" in hat_j

    hat_k = MathParser.parse_math_to_html(r"\hat{\kappa}")
    assert "k&#x0302;" in hat_k


def test_fractions_and_roots():
    # Simple fraction
    frac_half = MathParser.parse_math_to_html(r"\tfrac{1}{2}")
    assert "&frac12;" in frac_half or "1" in frac_half

    # Complex fraction
    frac_complex = MathParser.parse_math_to_html(r"\frac{\vec{a}\cdot\vec{b}}{|\vec{a}|}")
    assert "math-fraction" in frac_complex
    assert "table" in frac_complex

    # Square root
    sqrt_html = MathParser.parse_math_to_html(r"\sqrt{a^2 + b^2}")
    assert "&radic;" in sqrt_html
    assert "border-top" in sqrt_html


def test_matrices_and_determinants():
    # 2D Vector column matrix / pmatrix
    pmatrix_html = MathParser.parse_math_to_html(r"\begin{pmatrix} a \\ b \end{pmatrix}")
    assert "math-matrix" in pmatrix_html
    assert "pmatrix" in pmatrix_html
    assert "table" in pmatrix_html

    # 3D Determinant / vmatrix
    vmatrix_html = MathParser.parse_math_to_html(r"\begin{vmatrix} \hat{\imath} & \hat{\jmath} & \hat{\kappa} \\ a_1 & a_2 & a_3 \\ b_1 & b_2 & b_3 \end{vmatrix}")
    assert "math-matrix" in vmatrix_html
    assert "vmatrix" in vmatrix_html


def test_delimiters_and_subscripts():
    # Angle brackets
    angle_html = MathParser.parse_math_to_html(r"\langle 3, 4 \rangle")
    assert "⟨" in angle_html or "&lang;" in angle_html
    assert "⟩" in angle_html or "&rang;" in angle_html

    # Subscripts and superscripts
    sub_html = MathParser.parse_math_to_html(r"c_1\vec{v}_1 + c_2\vec{v}_2")
    assert "<sub>" in sub_html
    assert "math-vector" in sub_html


def test_markdown_with_math_rendering():
    theme = ThemeConfig(is_dark_background=True, text_color="#F8FAFC", backing_tint="rgba(15, 23, 42, 0.8)")

    markdown_input = r"""# Vectors Tutorial

In the 2D plane, a vector is written as:
$$\vec{v} = \langle a, b \rangle \quad \text{or} \quad \begin{pmatrix} a \\ b \end{pmatrix}$$

Magnitude:
$$|\vec{v}| = \sqrt{a^2 + b^2}$$

Unit vector: $\hat{v} = \frac{\vec{v}}{|\vec{v}|}$ and $\mathbb{R}^4$.

Code block should not parse math:
```python
# $x = 10$ and $$y = 20$$
def calc():
    return "$100"
```
"""

    rendered = render_markdown_with_math(markdown_input, theme=theme)

    # Verify headers
    assert "<h1>Vectors Tutorial</h1>" in rendered or "Vectors Tutorial" in rendered

    # Verify display math
    assert "math-display" in rendered
    assert "math-vector" in rendered
    assert "math-matrix" in rendered

    # Verify roots and inline math
    assert "&radic;" in rendered
    assert "ℝ" in rendered

    # Verify code block was protected and highlighted
    assert "calc" in rendered
    assert "$100" in rendered
    assert "<pre" in rendered


def test_user_vector_example_complete():
    """Tests that the user's vector introduction prompt renders without errors."""
    sample_text = r"""Vectors — A Patient, Ground-Up Introduction
1. The Core Idea: A Vector Is a "Directed Quantity"
Forget algebra for a moment. Think physically.
You push a box 3 meters to the right. That's a vector.
A car travels 60 km/h heading north. That's a vector.
Wind blows 15 m/s from the west. That's a vector.

2. How We Write One Down (Coordinates)
In the x–y plane (a flat 2D grid), a vector is written as an ordered pair:
$$\vec{v} = \langle a,; b \rangle \quad \text{or} \quad \begin{pmatrix} a \ b \end{pmatrix}$$
Example: $\vec{v} = \langle 3,; 4 \rangle$ means "go 3 units right, 4 units up."
Magnitude (length)
Use the Pythagorean theorem:
$$|\vec{v}| = \sqrt{a^2 + b^2}$$
For $\langle 3, 4 \rangle$: $;|v| = \sqrt{9+16} = \sqrt{25} = 5$. Good, that's our classic 3-4-5 triangle.

4. Unit Vectors and the Standard Basis
$$\hat{v} = \frac{\vec{v}}{|\vec{v}|}$$
$$\hat{\imath} = \langle 1, 0 \rangle \quad\text{(pointing right)}$$ $$\hat{\jmath} = \langle 0, 1 \rangle \quad\text{(pointing up)}$$
$$\vec{v} = \langle a, b\rangle = a,\hat{\imath} + b,\hat{\jmath}$$
In 3D we add $\hat{\kappa} = \langle 0,0,1\rangle$.

5. The Dot Product (This Is the Big One)
$$\vec{a} \cdot \vec{b} = |\vec{a}|;|\vec{b}|;\cos\theta$$
$$\text{comp}_{\vec{a}}\vec{b} = \frac{\vec{a}\cdot\vec{b}}{|\vec{a}|}$$
$$\text{proj}_{\vec{a}}\vec{b} = \frac{\vec{a}\cdot\vec{b}}{|\vec{a}|^2};\vec{a}$$

6. The Cross Product (3D Only)
$$\vec{a} \times \vec{b} = \begin{vmatrix} \hat{\imath} & \hat{\jmath} & \hat{\kappa} \ a_1 & a_2 & a_3 \ b_1 & b_2 & b_3 \end{vmatrix}$$

7. Vectors in Higher Dimensions
$\mathbb{R}^4$ and $\mathbb{R}^n$.

8. Linear Combinations, Spanning, Independence
$$c_1\vec{v}_1 + c_2\vec{v}_2 + \cdots + c_n\vec{v}_n$$
"""

    rendered = render_markdown_with_math(sample_text)
    assert len(rendered) > 1000
    assert "math-vector" in rendered
    assert "&radic;" in rendered
    assert "ℝ" in rendered
    assert "math-matrix" in rendered


def test_calculus_and_functions():
    # Integrals and limits
    int_html = MathParser.parse_math_to_html(r"\int_0^\infty e^{-x} dx = 1")
    assert "∫" in int_html
    assert "∞" in int_html

    # Summations
    sum_html = MathParser.parse_math_to_html(r"\sum_{i=1}^n i = \frac{n(n+1)}{2}")
    assert "∑" in sum_html

    # Partial derivatives and gradient
    grad_html = MathParser.parse_math_to_html(r"\nabla \cdot \vec{F} = \frac{\partial F_x}{\partial x}")
    assert "∇" in grad_html
    assert "∂" in grad_html

    # Functions and Binomial
    fn_html = MathParser.parse_math_to_html(r"\sin^2\theta + \cos^2\theta = 1")
    assert "sin" in fn_html
    assert "cos" in fn_html
    assert "θ" in fn_html

    binom_html = MathParser.parse_math_to_html(r"\binom{n}{k} = \frac{n!}{k!(n-k)!}")
    assert "math-matrix" in binom_html or "table" in binom_html


def test_streaming_partial_math():
    """Tests that unclosed trailing math markers during streaming don't crash and preview nicely."""
    partial_display = r"The formula is $$\vec{v} = \langle 3, 4"
    rendered_disp = render_markdown_with_math(partial_display)
    assert "math-vector" in rendered_disp or "math-display" in rendered_disp

    partial_inline = r"In 2D plane $x + y"
    rendered_inline = render_markdown_with_math(partial_inline)
    assert "math-inline" in rendered_inline


def test_escapes_and_unrecognized_macros():
    """Tests that formulas with raw backslashes (like \\hat, \\hspace, \\hbar, \\x) never cause re.PatternError."""
    text_with_escapes = r"""
Here is display math:
$$\hat{\boldsymbol{v}} = \frac{\hbar}{\sqrt{2m}} + \hspace{10px} \text{test} \unknownMacro$$

Here is code with escapes:
```python
regex = r"\d+\s+\h+\w+"
```
"""
    rendered = render_markdown_with_math(text_with_escapes)
    assert "math-display" in rendered
    assert "ℏ" in rendered
    assert r"\d+\s+\h+\w+" in rendered


def test_norms_sizing_delimiters_and_dots():
    """Tests \\| norm notation, sizing delimiters (\\bigl, \\bigr, \\Bigl, \\Bigr), and dots."""
    # User's reported case
    raw = r"\|v⃗\|_∞ = \max\bigl(|v1|,\|v2|, \dots,\|vn\|\bigr)"
    rendered = render_markdown_with_math(raw)
    assert "‖" in rendered
    assert "∞" in rendered
    assert "max" in rendered
    assert "…" in rendered
    assert "s&#x0307;" not in rendered
    assert "bigl" not in rendered
    assert "bigr" not in rendered

    # Sizing with brackets and fractions
    expr = r"$$\|\vec{x}\|_2 = \sqrt{\sum_{i=1}^n |x_i|^2} \quad \text{and} \quad \max\Bigl(\frac{a}{b}, \frac{c}{d}\Bigr)$$"
    rendered_disp = render_markdown_with_math(expr)
    assert "‖" in rendered_disp
    assert "math-display" in rendered_disp
    assert "&radic;" in rendered_disp
    assert "Bigl" not in rendered_disp
    assert "Bigr" not in rendered_disp




