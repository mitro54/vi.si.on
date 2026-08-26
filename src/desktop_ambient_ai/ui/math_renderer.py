"""
Math and Markdown rendering engine with high-fidelity LaTeX support for PyQt6 QTextEdit.

Converts markdown, code blocks, and mathematical notation (vectors, matrices, determinants,
fractions, roots, Greek letters, operators, accents, norms, and blackboard bold sets) into styled rich HTML.
"""

from __future__ import annotations

import html
import re
from typing import ClassVar

import markdown_it
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

from ..vision.spatial_finder import ThemeConfig

_PYGMENTS_CACHE: dict[tuple[str, str], str] = {}


def _highlight_code(code_content: str, lang: str) -> str:
    """Highlights code using Pygments with in-memory caching to avoid re-lexing during streaming."""
    key = (lang, code_content)
    if key in _PYGMENTS_CACHE:
        return _PYGMENTS_CACHE[key]

    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code_content)
    except (ClassNotFound, ValueError, TypeError, KeyError):
        lexer = TextLexer()

    formatter = HtmlFormatter(nowrap=True, noclasses=True)
    highlighted = highlight(code_content, lexer, formatter)

    if len(_PYGMENTS_CACHE) > 300:
        _PYGMENTS_CACHE.clear()
    _PYGMENTS_CACHE[key] = highlighted
    return highlighted


class MathParser:

    """High-fidelity LaTeX math parser producing clean, styled rich HTML/Unicode for Qt rich text."""

    GREEK: ClassVar[dict[str, str]] = {
        "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "varepsilon": "ε",
        "zeta": "ζ", "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
        "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π", "varpi": "ϖ",
        "rho": "ρ", "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ", "upsilon": "υ",
        "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
        "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π",
        "Sigma": "Σ", "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω"
    }

    BLACKBOARD: ClassVar[dict[str, str]] = {
        "R": "ℝ", "C": "ℂ", "N": "ℕ", "Z": "ℤ", "Q": "ℚ", "P": "ℙ", "E": "𝔼", "H": "ℍ", "F": "𝔽"
    }

    SYMBOLS: ClassVar[dict[str, str]] = {
        "cdot": "·", "times": "×", "div": "÷", "pm": "±", "mp": "∓",
        "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠",
        "approx": "≈", "equiv": "≡", "sim": "∼", "simeq": "≃", "cong": "≅", "propto": "∝",
        "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆", "supset": "⊃", "supseteq": "⊇",
        "cup": "∪", "cap": "∩", "setminus": "∖", "emptyset": "∅", "varnothing": "∅",
        "forall": "∀", "exists": "∃", "nexists": "∄", "infty": "∞",
        "partial": "∂", "nabla": "∇",
        "sum": "∑", "prod": "∏", "coprod": "∐",
        "int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮",
        "to": "→", "rightarrow": "→", "leftarrow": "←", "leftrightarrow": "↔",
        "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔",
        "Longrightarrow": "⟹", "Longleftarrow": "⟸", "Longleftrightarrow": "⟺",
        "mapsto": "↦", "uparrow": "↑", "downarrow": "↓", "updownarrow": "↕",
        "angle": "∠", "parallel": "∥", "perp": "⊥",
        "circ": "∘", "bullet": "•", "star": "⋆", "ast": "*",
        "oplus": "⊕", "otimes": "⊗", "odot": "⊙",
        "hbar": "ℏ", "ell": "ℓ", "Re": "ℜ", "Im": "ℑ", "aleph": "ℵ", "wp": "℘",
        "Box": "□", "diamond": "◇", "top": "⊤", "bot": "⊥", "vdash": "⊢", "vDash": "⊨", "models": "⊨",
        "langle": "⟨", "rangle": "⟩",
        "lbrace": "{", "rbrace": "}",
        "quad": "&emsp;", "qquad": "&emsp;&emsp;",
        ",": "&thinsp;", ";": "&nbsp;&nbsp;", ":": "&nbsp;", " ": "&nbsp;", "!": "",
        "hline": ""
    }

    FUNCTIONS: ClassVar[list[str]] = [
        "sin", "cos", "tan", "sec", "csc", "cot",
        "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh",
        "ln", "log", "exp", "lim", "max", "min", "sup", "inf",
        "det", "dim", "ker", "deg", "gcd", "arg", "mod", "Pr", "comp", "proj", "Tr", "trace"
    ]

    @classmethod
    def _extract_braced_arg(cls, s: str, start_idx: int) -> tuple[str, int]:
        """Extracts {arg} starting at start_idx (or first non-whitespace char)."""
        idx = start_idx
        while idx < len(s) and s[idx].isspace():
            idx += 1
        if idx >= len(s):
            return "", idx
        if s[idx] == '{':
            depth = 1
            idx += 1
            start = idx
            while idx < len(s) and depth > 0:
                if s[idx] == '{':
                    depth += 1
                elif s[idx] == '}':
                    depth -= 1
                    if depth == 0:
                        return s[start:idx], idx + 1
                idx += 1
            return s[start:idx], idx
        else:
            if s[idx] == '\\':
                m = re.match(r'^\\[a-zA-Z]+', s[idx:])
                if m:
                    return m.group(0), idx + len(m.group(0))
            return s[idx], idx + 1

    @classmethod
    def parse_math_to_html(cls, latex: str, is_display: bool = False) -> str:
        """Translates a LaTeX mathematical string into styled rich HTML."""
        s = latex.strip()
        if not s:
            return ""

        # Normalize common LaTeX formatting quirks
        s = re.sub(r',\s*;\s*', ', ', s)
        s = re.sub(r';\s*\\', r' \\', s)
        s = re.sub(r'\\([a-zA-Z]+);', r'\\\1 ', s)
        s = re.sub(r';\s*\|', '|', s)
        s = re.sub(r';\s*$', '', s)

        # 1. Delimiter Sizing Modifiers (\bigl, \bigr, \Bigl, \Bigr, \biggl, \biggr, \Biggl, \Biggr, \bigm, \Bigm, \biggm, \Biggm, \big, \Big, \bigg, \Bigg)
        s = re.sub(r'\\(big|Big|bigg|Bigg)[lrgm]?\s*\\\|', '‖', s)
        s = re.sub(r'\\(big|Big|bigg|Bigg)[lrgm]?\s*\\\{', '{', s)
        s = re.sub(r'\\(big|Big|bigg|Bigg)[lrgm]?\s*\\\}', '}', s)
        s = re.sub(r'\\(big|Big|bigg|Bigg)[lrgm]?\s*\\langle', '⟨', s)
        s = re.sub(r'\\(big|Big|bigg|Bigg)[lrgm]?\s*\\rangle', '⟩', s)
        s = re.sub(r'\\(big|Big|bigg|Bigg)[lrgm]?\s*([()\[\]|])', r'\2', s)
        s = re.sub(r'\\(big|Big|bigg|Bigg)[lrgm]?', '', s)

        # 2. Norms and Delimiters (\left, \right, \middle, \|, \lVert, \rVert, \Vert)
        s = re.sub(r'\\left\s*\\\|', '‖', s)
        s = re.sub(r'\\right\s*\\\|', '‖', s)
        s = re.sub(r'\\middle\s*\\\|', '‖', s)
        s = re.sub(r'\\left\s*\\langle', '⟨', s)
        s = re.sub(r'\\right\s*\\rangle', '⟩', s)
        s = re.sub(r'\\left\s*([(\[{|])', r'\1', s)
        s = re.sub(r'\\right\s*([)\]}|])', r'\1', s)
        s = re.sub(r'\\left\.', '', s)
        s = re.sub(r'\\right\.', '', s)
        s = re.sub(r'\\\|', '‖', s)
        s = re.sub(r'\\(lVert|rVert|Vert)', '‖', s)
        s = re.sub(r'\\(lvert|rvert|vert|mid)', '|', s)

        # 3. Dots (MUST be parsed before \dot accent to prevent \dots becoming \dot{s})
        s = re.sub(r'\\(dots|ldots|cdots|dotsb|dotsc|dotsi|dotso|dotsm)(?![a-zA-Z])', '…', s)
        s = re.sub(r'\\vdots(?![a-zA-Z])', '⋮', s)
        s = re.sub(r'\\ddots(?![a-zA-Z])', '⋱', s)

        # 4. Handle Matrix Environments (pmatrix, bmatrix, vmatrix, matrix, cases)
        def replace_matrix(match: re.Match) -> str:
            env = match.group(1)
            content = match.group(2)
            rows = [r.strip() for r in re.split(r'\\\\|(?<=[^\\])\\\s+(?=[a-zA-Z0-9\\])', content) if r.strip()]
            table_rows = []
            for row in rows:
                if not row.strip():
                    continue
                cols = [c.strip() for c in row.split('&')]
                parsed_cols = [cls.parse_math_to_html(c, is_display=False) for c in cols]
                tds = "".join([f'<td align="center" style="padding: 1px 6px;">{c}</td>' for c in parsed_cols])
                table_rows.append(f"<tr>{tds}</tr>")

            tbody = "".join(table_rows)
            border_style = "border-left: 2px solid currentColor; border-right: 2px solid currentColor; border-radius: 8px;"
            if env == "vmatrix":
                border_style = "border-left: 1.5px solid currentColor; border-right: 1.5px solid currentColor; border-radius: 0px;"
            elif env == "bmatrix":
                border_style = "border-left: 2px solid currentColor; border-right: 2px solid currentColor; border-radius: 2px;"
            elif env == "matrix":
                border_style = ""
            elif env == "cases":
                border_style = "border-left: 2px solid currentColor; border-radius: 0px;"

            return (
                f'<table class="math-matrix {env}" border="0" style="display:inline-table; '
                f'vertical-align:middle; {border_style} margin: 0 4px; padding: 2px 4px;">{tbody}</table>'
            )

        s = re.sub(
            r'\\begin\{(pmatrix|bmatrix|vmatrix|matrix|cases)\}(.*?)\\end\{\1\}',
            replace_matrix,
            s,
            flags=re.DOTALL
        )

        # 5. Handle text blocks (\text{...}, \mathrm{...}, \operatorname{...})
        def replace_text(match: re.Match) -> str:
            txt = match.group(2)
            return f'<span style="font-style: normal; font-family: inherit;">{html.escape(txt)}</span>'
        s = re.sub(r'\\(text|mathrm|operatorname)\{([^{}]*)\}', replace_text, s)

        # 6. Handle Blackboard Bold (\mathbb{R}, \mathbb{C}, etc.)
        def replace_mathbb(match: re.Match) -> str:
            arg = match.group(1)
            return "".join([cls.BLACKBOARD.get(c, c) for c in arg])
        s = re.sub(r'\\mathbb\{([A-Za-z]+)\}', replace_mathbb, s)

        # 7. Handle font styles (\mathbf, \boldsymbol, \bm, \mathit, \mathtt)
        s = re.sub(r'\\(mathbf|boldsymbol|bm)\{([^{}]*)\}', lambda m: f'<b>{cls.parse_math_to_html(m.group(2))}</b>', s)
        s = re.sub(r'\\mathit\{([^{}]*)\}', lambda m: f'<i>{cls.parse_math_to_html(m.group(2))}</i>', s)
        s = re.sub(r'\\mathtt\{([^{}]*)\}', lambda m: f'<code>{html.escape(m.group(1))}</code>', s)

        # 8. Handle Fractions (\frac, \tfrac, \dfrac, \binom)
        while True:
            m = re.search(r'\\(frac|tfrac|dfrac|binom)', s)
            if not m:
                break
            cmd_type = m.group(1)
            cmd_start = m.start()
            cmd_end = m.end()
            num, idx1 = cls._extract_braced_arg(s, cmd_end)
            den, idx2 = cls._extract_braced_arg(s, idx1)
            parsed_num = cls.parse_math_to_html(num, is_display=False)
            parsed_den = cls.parse_math_to_html(den, is_display=False)

            if cmd_type == "binom":
                frac_html = (
                    f'<table class="math-matrix" border="0" style="display:inline-table; vertical-align:middle; '
                    f'border-left:1.5px solid currentColor; border-right:1.5px solid currentColor; border-radius:6px; margin:0 3px;">'
                    f'<tr><td align="center" style="padding:0 3px; line-height:1.05;">{parsed_num}</td></tr>'
                    f'<tr><td align="center" style="padding:0 3px; line-height:1.05;">{parsed_den}</td></tr>'
                    f'</table>'
                )
            elif num.isdigit() and den.isdigit() and len(num) == 1 and len(den) == 1:
                if num == "1" and den == "2":
                    frac_html = "&frac12;"
                elif num == "1" and den == "4":
                    frac_html = "&frac14;"
                elif num == "3" and den == "4":
                    frac_html = "&frac34;"
                elif num == "1" and den == "3":
                    frac_html = "&#x2153;"
                elif num == "2" and den == "3":
                    frac_html = "&#x2154;"
                else:
                    frac_html = f'<sup>{parsed_num}</sup>/<sub>{parsed_den}</sub>'
            else:
                frac_html = (
                    f'<table class="math-fraction" border="0" style="display:inline-table; vertical-align:middle; text-align:center; border-collapse:collapse; margin:0 3px;">'
                    f'<tr><td style="border-bottom:1px solid currentColor; padding:0 3px; line-height:1.05;">{parsed_num}</td></tr>'
                    f'<tr><td style="padding:0 3px; line-height:1.05;">{parsed_den}</td></tr>'
                    f'</table>'
                )
            s = s[:cmd_start] + frac_html + s[idx2:]

        # 9. Handle Square Roots & N-th Roots (\sqrt, \sqrt[n])
        while True:
            m = re.search(r'\\sqrt(?:\[([^\]]*)\])?', s)
            if not m:
                break
            cmd_start = m.start()
            cmd_end = m.end()
            root_deg = m.group(1)
            inner, idx = cls._extract_braced_arg(s, cmd_end)
            parsed_inner = cls.parse_math_to_html(inner, is_display=False)
            if root_deg:
                parsed_deg = cls.parse_math_to_html(root_deg, is_display=False)
                sqrt_html = f'<sup>{parsed_deg}</sup>&radic;<span style="border-top:1px solid currentColor; padding-top:1px; margin-left:1px;">{parsed_inner}</span>'
            else:
                sqrt_html = f'&radic;<span style="border-top:1px solid currentColor; padding-top:1px; margin-left:1px;">{parsed_inner}</span>'
            s = s[:cmd_start] + sqrt_html + s[idx:]

        # 10. Handle Vector and Accent Notations (\vec, \hat, \bar, \dot, etc.)
        s = re.sub(r'\\(overrightarrow|widehat)\{([^{}]+)\}', r'\\vec{\2}', s)

        def replace_vec(match: re.Match) -> str:
            raw_arg = match.group(1) or match.group(2)
            arg = raw_arg.strip()
            if arg in (r'\imath', 'i'):
                arg_rendered = "i"
            elif arg in (r'\jmath', 'j'):
                arg_rendered = "j"
            else:
                arg_rendered = arg
            return f'<span class="math-vector"><b><i>{arg_rendered}</i></b>&#x20D7;</span>'
        s = re.sub(r'\\vec(?:\{([^{}]+)\}|\\?([a-zA-Z0-9]))', replace_vec, s)

        def replace_hat(match: re.Match) -> str:
            raw_arg = match.group(1) or match.group(2)
            arg = raw_arg.strip()
            if arg in (r'\imath', 'i'):
                return "<i>&#x0131;&#x0302;</i>"
            elif arg in (r'\jmath', 'j'):
                return "<i>&#x0237;&#x0302;</i>"
            elif arg in (r'\kappa', 'k'):
                return "<i>k&#x0302;</i>"
            return f'<i>{arg}&#x0302;</i>'
        s = re.sub(r'\\hat(?:\{([^{}]+)\}|\\?([a-zA-Z0-9]))', replace_hat, s)

        s = re.sub(r'\\(bar|overline)(?:\{([^{}]+)\}|([a-zA-Z0-9]))', lambda m: f'<i>{(m.group(2) or m.group(3))}&#x0304;</i>', s)
        s = re.sub(r'\\(underline)(?:\{([^{}]+)\}|([a-zA-Z0-9]))', lambda m: f'<u>{(m.group(2) or m.group(3))}</u>', s)
        s = re.sub(r'\\dot(?:\{([^{}]+)\}|([a-zA-Z0-9]))', lambda m: f'<i>{(m.group(1) or m.group(2))}&#x0307;</i>', s)
        s = re.sub(r'\\ddot(?:\{([^{}]+)\}|([a-zA-Z0-9]))', lambda m: f'<i>{(m.group(1) or m.group(2))}&#x0308;</i>', s)
        s = re.sub(r'\\tilde(?:\{([^{}]+)\}|([a-zA-Z0-9]))', lambda m: f'<i>{(m.group(1) or m.group(2))}&#x0303;</i>', s)

        # 11. Handle Standard Functions (sin, cos, exp, ln, max, min, etc.)
        for fn in cls.FUNCTIONS:
            s = re.sub(rf'\\{fn}(?![a-zA-Z])', f'<span style="font-style:normal;">{fn}</span> ', s)

        # 12. Handle Greek Letters
        for g_name, g_sym in cls.GREEK.items():
            s = re.sub(rf'\\{g_name}(?![a-zA-Z])', g_sym, s)

        # 13. Handle Symbols and Operators
        for sym_name, sym_val in cls.SYMBOLS.items():
            if sym_name in (",", ";", ":", " ", "!"):
                s = re.sub(rf'\\{re.escape(sym_name)}', sym_val, s)
            else:
                s = re.sub(rf'\\{sym_name}(?![a-zA-Z])', sym_val, s)

        # 14. Handle Escaped Braces
        s = s.replace(r'\{', '{').replace(r'\}', '}')

        # 15. Handle Superscripts and Subscripts (extended with Unicode characters like ∞, Greek letters, T, *)
        def replace_sup(match: re.Match) -> str:
            content = match.group(1) or match.group(2)
            parsed = cls.parse_math_to_html(content, is_display=False)
            return f'<sup>{parsed}</sup>'
        s = re.sub(r'\^(?:\{([^{}]+)\}|([a-zA-Z0-9+\-=∞α-ωΑ-Ω*T⊤⊥′]))', replace_sup, s)

        def replace_sub(match: re.Match) -> str:
            content = match.group(1) or match.group(2)
            parsed = cls.parse_math_to_html(content, is_display=False)
            return f'<sub>{parsed}</sub>'
        s = re.sub(r'_(?:\{([^{}]+)\}|([a-zA-Z0-9+\-=∞α-ωΑ-Ω*]))', replace_sub, s)

        # 16. Convert Standalone Single Letters into Math Italic (only outside existing styling tags)
        tokens = re.split(r'(<[^>]+>|&[a-zA-Z0-9#]+;)', s)
        formatted_parts = []
        suppress_italic_depth = 0

        for t in tokens:
            if not t:
                continue
            if t.startswith('<'):
                if re.match(r'<(i|b|code|pre|span|td|table|tr|div)\b[^>]*>', t, re.IGNORECASE):
                    if re.match(r'<(i|b|code|pre|span)\b[^>]*>', t, re.IGNORECASE):
                        suppress_italic_depth += 1
                elif re.match(r'</(i|b|code|pre|span)\b[^>]*>', t, re.IGNORECASE):
                    suppress_italic_depth = max(0, suppress_italic_depth - 1)
                formatted_parts.append(t)
            elif t.startswith('&'):
                formatted_parts.append(t)
            else:
                if suppress_italic_depth > 0:
                    formatted_parts.append(t)
                else:
                    t = re.sub(r'\b([a-zA-Z])\b', r'<i>\1</i>', t)
                    formatted_parts.append(t)
        s = "".join(formatted_parts)

        # 17. Clean up spacing & phantom macros, and normalize remaining commands
        s = re.sub(r'\\(phantom|vspace)\{[^{}]*\}', '', s)
        s = re.sub(r'\\hspace\{[^{}]*\}', '&nbsp;', s)
        s = re.sub(r'\\([a-zA-Z]+)', r'\1', s)

        # Output Wrap
        if is_display:
            return (
                f'<div class="math-display" style="margin: 8px 0; text-align: center; '
                f'font-family: \'Cambria Math\', \'STIX Two Math\', \'Segoe UI Historic\', \'Times New Roman\', serif; font-size: 1.06em;">'
                f'{s}</div>'
            )
        else:
            return (
                f'<span class="math-inline" style="font-family: \'Cambria Math\', \'STIX Two Math\', \'Segoe UI Historic\', \'Times New Roman\', serif;">'
                f'{s}</span>'
            )


def _wrap_unwrapped_math_lines(text: str) -> str:
    """Detects lines containing unwrapped raw LaTeX math equations and wraps them into display math blocks."""
    lines = text.split('\n')
    new_lines = []
    math_indicators = re.compile(
        r'(?:\\(?:vec|hat|bar|dot|ddot|tilde|frac|tfrac|dfrac|sqrt|sum|prod|int|'
        r'alpha|beta|gamma|delta|epsilon|varepsilon|zeta|eta|theta|vartheta|iota|kappa|lambda|mu|nu|xi|pi|varpi|'
        r'rho|varrho|sigma|varsigma|tau|upsilon|phi|varphi|chi|psi|omega|Gamma|Delta|Theta|Lambda|Xi|Pi|Sigma|Upsilon|Phi|Psi|Omega|'
        r'infty|partial|nabla|cdot|times|div|pm|mp|le|leq|ge|geq|neq|ne|approx|equiv|sim|simeq|cong|propto|'
        r'in|notin|subset|subseteq|supset|supseteq|cup|cap|to|rightarrow|leftarrow|Rightarrow|Leftarrow|Leftrightarrow|Longleftrightarrow|'
        r'mathbb|mathbf|boldsymbol|mathit|mathtt|mathrm|text|operatorname|'
        r'sin|cos|tan|arcsin|arccos|arctan|ln|log|exp|lim|max|min|sup|inf|det|dim|ker|deg|gcd|'
        r'langle|rangle|hbar|ell|Re|Im|lVert|rVert|Vert|vert|lvert|rvert|bigl|bigr|Bigl|Bigr|biggl|biggr|Biggl|Biggr|left|right)|\\\|)'
    )

    for line in lines:
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith(('#', '```', '*', '-', '>', '|', '@@@'))
            and not (stripped.startswith('$') and stripped.endswith('$'))
            and math_indicators.search(stripped)
            and any(k in stripped for k in ['=', r'\le', r'\ge', r'\in', r'\to', r'\approx', r'\equiv', r'\neq', r'\|', r'\sum', r'\int', r'\frac', r'\sqrt'])
        ):
            line = f"$${stripped}$$"
        new_lines.append(line)

    return '\n'.join(new_lines)


def render_markdown_with_math(markdown_text: str, theme: ThemeConfig | None = None) -> str:
    """
    Parses full markdown document with embedded LaTeX formulas into rich HTML for Qt QTextEdit.

    Protects code blocks, handles display/inline equations, applies Pygments syntax highlighting,
    and formats mathematical symbols.
    """
    if not markdown_text:
        return ""

    text = markdown_text

    # Streaming UX enhancement: If there is an unclosed math block at the end during streaming, close it for rendering
    if text.count("$$") % 2 == 1:
        text += "$$"
    elif text.count("$") % 2 == 1 and not text.endswith("\\$"):
        text += "$"

    # 1. Protect Code Blocks (both fenced and inline)
    code_blocks: list[str] = []
    def save_code_block(match: re.Match) -> str:
        code_blocks.append(match.group(0))
        return f"@@@CODE_BLOCK_{len(code_blocks)-1}@@@"

    text = re.sub(r'```[^\n]*\n.*?```', save_code_block, text, flags=re.DOTALL)
    text = re.sub(r'`[^`\n]+`', save_code_block, text)

    # 2. Extract and Protect Display Math ($$...$$, \[...\], \begin{equation}...\end{equation})
    display_math_blocks: list[str] = []
    def save_display_math(match: re.Match) -> str:
        inner = match.group(1).strip()
        display_math_blocks.append(inner)
        return f"\n\n@@@DISPLAY_MATH_{len(display_math_blocks)-1}@@@\n\n"

    text = re.sub(r'\$\$(.*?)\$\$', save_display_math, text, flags=re.DOTALL)
    text = re.sub(r'\\\[(.*?)\\\]', save_display_math, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}', save_display_math, text, flags=re.DOTALL)
    text = re.sub(r'\\begin\{align\*?\}(.*?)\\end\{align\*?\}', save_display_math, text, flags=re.DOTALL)

    # Standalone matrix/determinant blocks outside math tags
    def save_matrix_block(match: re.Match) -> str:
        inner = match.group(0).strip()
        display_math_blocks.append(inner)
        return f"\n\n@@@DISPLAY_MATH_{len(display_math_blocks)-1}@@@\n\n"

    text = re.sub(
        r'\\begin\{(pmatrix|bmatrix|vmatrix|matrix|cases)\}.*?\\end\{\1\}',
        save_matrix_block,
        text,
        flags=re.DOTALL
    )

    # 3. Extract and Protect Inline Math ($...$, \(...\))
    inline_math_blocks: list[str] = []
    def save_inline_math(match: re.Match) -> str:
        inner = match.group(1).strip()
        inline_math_blocks.append(inner)
        return f"@@@INLINE_MATH_{len(inline_math_blocks)-1}@@@"

    # Match $...$ where it is not preceded by \ and does not match empty/currency-only
    text = re.sub(r'(?<!\\)\$([^\$\n]+?)(?<!\\)\$', save_inline_math, text)
    text = re.sub(r'\\\((.*?)\\\)', save_inline_math, text)

    # 4. Detect and Wrap Unwrapped Math Equations into Display Math
    text = _wrap_unwrapped_math_lines(text)
    text = re.sub(r'\$\$(.*?)\$\$', save_display_math, text, flags=re.DOTALL)

    # 5. Render Markdown Structure using MarkdownIt (with tables and strikethrough enabled)
    md = (
        markdown_it.MarkdownIt("commonmark", {"breaks": True, "html": True})
        .enable("table")
        .enable("strikethrough")
    )
    rendered_html = md.render(text)

    # 6. Restore Display Math (using lambda replacement to avoid re.sub backslash escape errors)
    for idx, raw_math in enumerate(display_math_blocks):
        math_html = MathParser.parse_math_to_html(raw_math, is_display=True)
        rendered_html = re.sub(
            rf'<p>\s*@@@DISPLAY_MATH_{idx}@@@\s*</p>',
            lambda _m, h=math_html: h,
            rendered_html,
        )
        rendered_html = rendered_html.replace(f"@@@DISPLAY_MATH_{idx}@@@", math_html)

    # 7. Restore Inline Math
    for idx, raw_math in enumerate(inline_math_blocks):
        math_html = MathParser.parse_math_to_html(raw_math, is_display=False)
        rendered_html = rendered_html.replace(f"@@@INLINE_MATH_{idx}@@@", math_html)

    # 8. Restore Code Blocks with Pygments Syntax Highlighting
    is_dark = bool(not theme or theme.is_dark_background)
    code_bg = "rgba(30, 41, 59, 0.75)" if is_dark else "rgba(241, 245, 249, 0.9)"
    code_color = "#38BDF8" if is_dark else "#0284C7"

    for idx, code_raw in enumerate(code_blocks):
        if code_raw.startswith("```"):
            m = re.match(r'^```([a-zA-Z0-9_-]*)\n(.*?)```$', code_raw, flags=re.DOTALL)
            if m:
                lang = m.group(1).strip()
                code_content = m.group(2)
                highlighted = _highlight_code(code_content, lang)
                block_html = (
                    f'<pre style="background-color: {code_bg}; color: {code_color}; '
                    f'border-radius: 8px; padding: 10px 12px; margin: 8px 0; '
                    f'font-family: \'Cascadia Code\', \'Consolas\', monospace; font-size: 13px;">'
                    f'<code>{highlighted}</code></pre>'
                )


            else:
                block_html = f'<pre><code>{html.escape(code_raw)}</code></pre>'
        else:
            inner_code = code_raw[1:-1]
            block_html = (
                f'<code style="background-color: {code_bg}; color: {code_color}; '
                f'border-radius: 4px; padding: 2px 5px; '
                f'font-family: \'Cascadia Code\', \'Consolas\', monospace; font-size: 0.92em;">'
                f'{html.escape(inner_code)}</code>'
            )

        rendered_html = re.sub(
            rf'<p>\s*@@@CODE_BLOCK_{idx}@@@\s*</p>',
            lambda _m, h=block_html: h,
            rendered_html,
        )
        rendered_html = rendered_html.replace(f"@@@CODE_BLOCK_{idx}@@@", block_html)

    # 9. Style Markdown Tables for Qt Rich Text
    border_col = "rgba(148, 163, 184, 0.25)" if is_dark else "rgba(100, 116, 139, 0.25)"
    head_bg = "rgba(30, 41, 59, 0.6)" if is_dark else "rgba(241, 245, 249, 0.8)"
    rendered_html = rendered_html.replace(
        "<table>",
        f'<table border="0" style="border-collapse: collapse; width: 100%; margin: 8px 0; border: 1px solid {border_col};">'
    )
    rendered_html = rendered_html.replace(
        "<th>",
        f'<th style="background-color: {head_bg}; padding: 4px 8px; border: 1px solid {border_col}; text-align: left; font-weight: 600;">'
    )
    rendered_html = rendered_html.replace(
        "<td>",
        f'<td style="padding: 4px 8px; border: 1px solid {border_col};">'
    )

    return rendered_html

