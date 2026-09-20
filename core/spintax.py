import re
import random
from typing import Dict, Any, List

class SpintaxEngine:
    """
    Parses spintax templates and handles variable interpolation.
    Example:
      "{Hey|Hello|Hi} {name}! {Hope you are well|Loved your content}."
    """

    # Matches only blocks that have an alternation bar '|' inside curly brackets
    SPINTAX_ALTERNATION_PATTERN = re.compile(r"\{([^{}]+?\|[^{}]+?)\}")

    @classmethod
    def spin(cls, template: str, variables: Dict[str, Any] = None) -> str:
        """
        Recursively resolves spintax and replaces variables.
        """
        if not template:
            return ""

        text = template

        # Replace dynamic variables first or during processing
        if variables:
            username = variables.get("username", "").strip().lstrip("@")
            name = variables.get("name", "").strip() or username
            first_name = name.split()[0] if name else username

            context = {
                "username": username,
                "name": name,
                "first_name": first_name,
                **variables
            }

            for key, val in context.items():
                pattern = re.compile(rf"\{{{re.escape(key)}\}}", re.IGNORECASE)
                text = pattern.sub(str(val), text)

        # Recursively resolve nested spintax brackets {opt1|opt2}
        while True:
            match = cls.SPINTAX_ALTERNATION_PATTERN.search(text)
            if not match:
                break
            options = match.group(1).split("|")
            chosen = random.choice(options)
            text = text[:match.start()] + chosen + text[match.end():]

        return text.strip()

    @classmethod
    def generate_previews(cls, template: str, count: int = 5, sample_vars: Dict[str, Any] = None) -> List[str]:
        """
        Generates sample outputs from a spintax template for previewing in the UI.
        """
        if sample_vars is None:
            sample_vars = {
                "username": "alex_growth",
                "name": "Alex Mercer",
                "first_name": "Alex"
            }
        
        previews = []
        for _ in range(count):
            previews.append(cls.spin(template, sample_vars))
        return previews
