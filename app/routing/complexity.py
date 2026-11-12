"""Complexity scoring for routing decisions."""


def score_complexity(prompt: str) -> float:
    """Score prompt complexity as a float from 0.0 to 1.0.

    Args:
        prompt: User's query text

    Returns:
        Complexity score:
        - 0.0-0.3: Simple (short, no keywords)
        - 0.3-0.7: Moderate (medium length or some keywords)
        - 0.7-1.0: Complex (long or many keywords)
    """
    # Count tokens (simple word-based approximation)
    token_count = len(prompt.split())

    # Keywords indicating complex queries
    complexity_keywords = [
        # Analysis & Reasoning
        "explain",
        "analyze",
        "compare",
        "design",
        "architecture",
        "evaluate",
        "critique",
        "research",
        "synthesize",
        "assess",
        "prove",
        "deduce",
        "infer",
        "conclude",
        "recommend",
        "suggest",
        # Code & Technical
        "implement",
        "debug",
        "optimize",
        "refactor",
        "algorithm",
        "function",
        "class",
        "method",
        "code",
        "api",
        "endpoint",
        "schema",
        "database",
        "query",
        "migration",
        "deploy",
        "configuration",
        "dependency",
        "package",
        "module",
        "component",
        # Problem Solving
        "solve",
        "calculate",
        "compute",
        "troubleshoot",
        "diagnose",
        "investigate",
        "fix",
        "repair",
        "resolve",
        "address",
        # Architecture & Systems
        "scalability",
        "performance",
        "security",
        "reliability",
        "availability",
        "infrastructure",
        "system",
        "distributed",
        "microservice",
        "pattern",
        "framework",
        "integration",
        # Complex Actions
        "reverse engineer",
        "benchmark",
        "profile",
        "migrate",
        "transform",
        "integrate",
        "construct",
        "build",
        "develop",
        # Creative & Strategic
        "create",
        "generate",
        "write",
        "compose",
        "draft",
        "strategy",
        "tradeoff",
        "decision",
        "prioritize",
        "roadmap",
    ]

    # Count complexity keywords found
    keywords_found = sum(1 for kw in complexity_keywords if kw in prompt.lower())

    # Calculate base score from token count (normalized to 0-0.5 range)
    # 40+ tokens = 0.5, linear scale below that
    token_score = min(token_count / 40.0 * 0.5, 0.5)

    # Calculate keyword score (normalized to 0-0.5 range)
    # Each keyword adds significant weight (1 keyword = 0.3)
    keyword_score = min(keywords_found * 0.3, 0.5)

    # Combine scores
    total_score = token_score + keyword_score

    # Clamp to [0.0, 1.0]
    return min(max(total_score, 0.0), 1.0)
