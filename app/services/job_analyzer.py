import re
from typing import List, Optional, Set
from app.models.schemas import JobAnalysisResult

# Predefined dictionary of technical and professional skills for matching
TECH_SKILLS: Set[str] = {
    "Python",
    "JavaScript",
    "TypeScript",
    "Java",
    "C++",
    "C#",
    "Ruby",
    "PHP",
    "Go",
    "Rust",
    "Swift",
    "Kotlin",
    "SQL",
    "NoSQL",
    "HTML",
    "CSS",
    "HTML5",
    "CSS3",
    "Sass",
    "Less",
    "React",
    "Angular",
    "Vue",
    "Next.js",
    "Nuxt.js",
    "Svelte",
    "Remix",
    "Gatsby",
    "Vite",
    "Node.js",
    "Express",
    "NestJS",
    "FastAPI",
    "Django",
    "Flask",
    "Spring Boot",
    "Laravel",
    "Ruby on Rails",
    "ASP.NET",
    ".NET",
    "Docker",
    "Kubernetes",
    "Terraform",
    "Ansible",
    "Chef",
    "Puppet",
    "Jenkins",
    "GitHub Actions",
    "GitLab CI",
    "CI/CD",
    "AWS",
    "Amazon Web Services",
    "GCP",
    "Google Cloud",
    "Google Cloud Platform",
    "Azure",
    "Microsoft Azure",
    "PostgreSQL",
    "MySQL",
    "SQLite",
    "MongoDB",
    "Redis",
    "Elasticsearch",
    "Cassandra",
    "DynamoDB",
    "Firebase",
    "Firestore",
    "Pydantic",
    "Streamlit",
    "Jinja2",
    "Pytest",
    "Ruff",
    "uv",
    "Pipenv",
    "Poetry",
    "Ollama",
    "Llama",
    "OpenAI",
    "LangChain",
    "Machine Learning",
    "Deep Learning",
    "Artificial Intelligence",
    "Natural Language Processing",
    "NLP",
    "Computer Vision",
    "Data Science",
    "Data Analysis",
    "Pandas",
    "NumPy",
    "Scikit-Learn",
    "TensorFlow",
    "PyTorch",
    "Keras",
    "REST API",
    "GraphQL",
    "gRPC",
    "WebSockets",
    "Microservices",
    "Serverless",
    "Git",
    "GitHub",
    "GitLab",
    "Bitbucket",
    "Linux",
    "Bash",
    "Shell",
    "PowerShell",
    "Agile",
    "Scrum",
    "Kanban",
    "Jira",
    "Trello",
    "Confluence",
    "Figma",
    "Adobe XD",
    "UI/UX",
    "Responsive Design",
    "Tailwind CSS",
    "Bootstrap",
    "Chakra UI",
    "Material UI",
    "TypeScript",
    "C",
    "Scala",
    "Haskell",
    "Elixir",
    "Clojure",
    "R",
    "MATLAB",
    "SAS",
    "COBOL",
    "Fortran",
    "Assembly",
    "Spanner",
    "BigQuery",
    "Snowflake",
    "Databricks",
    "Spark",
    "Hadoop",
    "Airflow",
    "Prefect",
    "Dagster",
    "Kafka",
    "RabbitMQ",
}

# Action verbs to identify responsibility lines
ACTION_VERBS: Set[str] = {
    "develop",
    "design",
    "maintain",
    "implement",
    "lead",
    "collaborate",
    "write",
    "support",
    "create",
    "deploy",
    "optimize",
    "build",
    "manage",
    "test",
    "integrate",
    "architect",
    "deliver",
    "configure",
    "monitor",
    "troubleshoot",
    "review",
    "improve",
    "scale",
    "coordinate",
    "oversee",
    "ensure",
    "analyze",
    "drive",
    "work",
    "participate",
    "define",
    "evaluate",
}

# Stop words to filter out during keyword extraction
STOP_WORDS: Set[str] = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "arent",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "cant",
    "cannot",
    "could",
    "couldnt",
    "did",
    "didnt",
    "do",
    "does",
    "doesnt",
    "doing",
    "dont",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "hadnt",
    "has",
    "hasnt",
    "have",
    "havent",
    "having",
    "he",
    "hed",
    "hell",
    "hes",
    "her",
    "here",
    "heres",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "hows",
    "i",
    "id",
    "ill",
    "im",
    "ive",
    "if",
    "in",
    "into",
    "is",
    "isnt",
    "it",
    "its",
    "itself",
    "lets",
    "me",
    "more",
    "most",
    "mustnt",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "ought",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "shant",
    "she",
    "shed",
    "shell",
    "shes",
    "should",
    "shouldnt",
    "so",
    "some",
    "such",
    "than",
    "that",
    "thats",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "theres",
    "these",
    "they",
    "theyd",
    "theyll",
    "theyre",
    "theyve",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "wasnt",
    "we",
    "wed",
    "well",
    "were",
    "weve",
    "werent",
    "what",
    "whats",
    "when",
    "whens",
    "where",
    "wheres",
    "which",
    "while",
    "who",
    "whos",
    "whom",
    "why",
    "whys",
    "with",
    "wont",
    "would",
    "wouldnt",
    "you",
    "youd",
    "youll",
    "youre",
    "youve",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "we're",
    "you're",
    "they're",
    "it's",
    "let's",
    "can't",
    "couldn't",
    "don't",
    "doesn't",
    "didn't",
    "hasn't",
    "haven't",
    "hadn't",
    "won't",
    "wouldn't",
    "shouldn't",
    "mustn't",
    "isn't",
    "aren't",
    "wasn't",
    "weren't",
    "job",
    "role",
    "work",
    "team",
    "project",
    "company",
    "candidate",
    "position",
    "skills",
    "experience",
    "required",
    "preferred",
    "duties",
    "responsibilities",
    "qualifications",
    "using",
    "working",
    "join",
    "building",
    "development",
    "developer",
    "engineer",
    "engineering",
    "systems",
    "system",
    "design",
    "build",
    "help",
    "ideal",
    "successful",
    "looking",
    "opportunity",
    "highly",
    "plus",
    "bonus",
}


def extract_skills(text: str) -> List[str]:
    """Finds all technical skills matching predefined dictionary inside the text.

    Uses regex lookarounds to handle symbol-containing skills like C++, C#,
    .NET.
    """
    found = []
    for skill in TECH_SKILLS:
        # Match boundaries while allowing symbols like C++, C#, .NET
        escaped = re.escape(skill)
        pattern = rf"(?<![a-zA-Z0-9]){escaped}(?![a-zA-Z0-9])"
        if re.search(pattern, text, re.IGNORECASE):
            found.append(skill)
    return sorted(found)


def extract_experience_requirement(text: str) -> Optional[float]:
    """Parses years of experience requirement from the text using regex heuristics.

    Returns the minimum required years of experience if found.
    """
    # Pattern to match: "X+ years", "X years", "X-Y years", etc. in experience contexts
    # We allow up to 3 optional words between "years/yrs" and "experience/exp/working" to support e.g. "years of software experience"
    pattern = re.compile(
        r"(?:minimum|at\s+least|min\.?|required|have)?\s*(\d+(?:\.\d+)?)\s*(?:\+|-|to)?\s*(?:\d+(?:\.\d+)?)?\s*(?:years?|yrs?)(?:\s+of)?(?:\s+\w+){0,3}\s+(?:experience|exp|working)\b",
        re.IGNORECASE,
    )

    matches = pattern.findall(text)

    # Fallback to broader match if context match not found
    if not matches:
        pattern_fallback = re.compile(
            r"\b(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?)\b",
            re.IGNORECASE,
        )
        matches = pattern_fallback.findall(text)

    if matches:
        years = []
        for m in matches:
            val = m[0] if isinstance(m, tuple) else m
            try:
                years.append(float(val))
            except ValueError:
                continue
        if years:
            valid = [y for y in years if y <= 25]
            if valid:
                return max(valid)
    return None


def extract_keywords(text: str, top_n: int = 15) -> List[str]:
    """Extracts the most frequent non-stop words as keywords."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    counts = {}
    for word in words:
        if word not in STOP_WORDS:
            counts[word] = counts.get(word, 0) + 1

    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:top_n]]


def analyze_job_description(text: str) -> JobAnalysisResult:
    """Analyzes job description text using rule-based parsing.

    Extracts required/preferred skills, responsibilities, experience years,
    and keywords.
    """
    # Classify required/preferred skills by sections or sentences
    lines = text.split("\n")
    current_section = "general"

    required_skills_set = set()
    preferred_skills_set = set()
    responsibilities = []

    # Regex patterns to categorize section headers
    req_header_re = re.compile(
        r"(?:requirements|qualifications|skills\s+required|who\s+you\s+are|must\s+have|what\s+you(?:\'ll|ll)\s+need)",
        re.IGNORECASE,
    )
    pref_header_re = re.compile(
        r"(?:preferred|nice\s+to\s+have|plus|bonus|desired|preferred\s+qualifications)",
        re.IGNORECASE,
    )
    resp_header_re = re.compile(
        r"(?:responsibilities|what\s+you\s+will\s+do|duties|the\s+role|key\s+tasks|what\s+you(?:\'ll|ll)\s+do)",
        re.IGNORECASE,
    )
    general_header_re = re.compile(
        r"(?:about\s+us|who\s+we\s+are|benefits|perks)", re.IGNORECASE
    )

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        # Check if line looks like a header
        is_header = False
        if (
            cleaned_line.startswith("#")
            or cleaned_line.startswith("**")
            and cleaned_line.endswith("**")
            or len(cleaned_line) < 50
        ):
            test_line = cleaned_line.lstrip("#* \t")
            if req_header_re.search(test_line):
                current_section = "required"
                is_header = True
            elif pref_header_re.search(test_line):
                current_section = "preferred"
                is_header = True
            elif resp_header_re.search(test_line):
                current_section = "responsibilities"
                is_header = True
            elif general_header_re.search(test_line):
                current_section = "general"
                is_header = True

        if is_header:
            continue

        # Extract responsibilities
        # Under a responsibilities section, any bullet point counts.
        # Otherwise, check if bullet starts with action verb.
        is_bullet = cleaned_line.startswith(("-", "*", "•", "1.", "2.", "3."))
        bullet_text = re.sub(
            r"^[-*•\s\d\.]+", "", cleaned_line
        ).strip()  # Clean bullet symbols

        if current_section == "responsibilities" and bullet_text:
            responsibilities.append(bullet_text)
        elif is_bullet and bullet_text:
            first_word = re.split(r"\W+", bullet_text)[0].lower()
            if first_word in ACTION_VERBS:
                responsibilities.append(bullet_text)

        # Extract skills in this line
        line_skills = extract_skills(cleaned_line)
        if line_skills:
            if current_section == "required":
                required_skills_set.update(line_skills)
            elif current_section == "preferred":
                preferred_skills_set.update(line_skills)
            else:
                # Fallback to sentence/line-level context clues
                if re.search(
                    r"\b(?:preferred|nice to have|plus|bonus|optional|desired|helpful)\b",
                    cleaned_line,
                    re.IGNORECASE,
                ):
                    preferred_skills_set.update(line_skills)
                else:
                    required_skills_set.update(line_skills)

    # Clean duplicates: if a skill is required, it shouldn't also be preferred
    preferred_skills_set.difference_update(required_skills_set)

    # Fallback: if no skills classified by line parsing, scan entire text
    if not required_skills_set and not preferred_skills_set:
        all_skills = extract_skills(text)
        # Without section tags, default to required
        required_skills_set.update(all_skills)

    # Extract years of experience
    experience_years = extract_experience_requirement(text)

    # Extract keywords
    keywords = extract_keywords(text)

    return JobAnalysisResult(
        required_skills=sorted(list(required_skills_set)),
        preferred_skills=sorted(list(preferred_skills_set)),
        responsibilities=responsibilities,
        experience_years_required=experience_years,
        keywords=keywords,
    )
