"""Regex and heuristic resume parser.

The project intentionally avoids spaCy so it can stay lightweight and easier to
install on newer Python releases. PDF text extraction is handled by pdfplumber;
field detection uses regular expressions, section parsing, and conservative
resume-specific heuristics.
"""

from __future__ import annotations

import re
from pathlib import Path

import pdfplumber


SKILLS_DB = [
    "Python", "Java", "JavaScript", "TypeScript", "C", "C++", "C#", "Go",
    "Rust", "PHP", "Ruby", "SQL", "NoSQL", "PostgreSQL", "MySQL", "SQLite",
    "MongoDB", "Redis", "HTML", "CSS", "Sass", "Tailwind", "Bootstrap",
    "React", "Vue", "Angular", "Node.js", "Express", "Flask", "Django",
    "FastAPI", "REST API", "GraphQL", "Docker", "Kubernetes", "AWS", "Azure",
    "Google Cloud", "Git", "Linux", "CI/CD", "Machine Learning",
    "Deep Learning", "Data Science", "Pandas", "NumPy", "TensorFlow",
    "PyTorch", "Scikit-learn", "Power BI", "Tableau", "Excel",
]

SECTION_HEADERS = {
    "education": ("education", "academic background", "academics"),
    "experience": (
        "experience", "work experience", "professional experience",
        "employment", "employment history", "internship", "internships",
    ),
    "skills": ("skills", "technical skills", "core skills", "technologies"),
    "certifications": ("certifications", "certification", "licenses"),
}

EDUCATION_HINTS = (
    "bachelor", "master", "phd", "doctorate", "b.tech", "m.tech", "b.sc",
    "m.sc", "bca", "mca", "mba", "university", "college", "institute",
    "school", "degree", "diploma", "cgpa", "gpa",
)

EXPERIENCE_HINTS = (
    "engineer", "developer", "analyst", "manager", "consultant", "intern",
    "associate", "lead", "specialist", "architect", "designed", "built",
    "developed", "implemented", "managed", "improved",
)

CERTIFICATION_HINTS = (
    "certified", "certificate", "certification", "aws", "azure",
    "google cloud", "oracle", "scrum", "pmp", "cisco",
)


class PDFParseError(Exception):
    """Raised when a PDF cannot be read as a resume."""


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Read selectable text from a PDF using pdfplumber."""
    path = Path(file_path)
    if not path.exists() or path.suffix.lower() != ".pdf":
        raise PDFParseError("Please upload a valid PDF file.")

    try:
        with pdfplumber.open(path) as pdf:
            text_parts = [
                page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                for page in pdf.pages
            ]
    except Exception as exc:
        raise PDFParseError("The PDF appears to be corrupted or unreadable.") from exc

    text = normalize_text("\n".join(text_parts))
    if not text:
        raise PDFParseError("No readable text was found in this PDF.")
    return text


def normalize_text(text: str) -> str:
    """Normalize noisy PDF text while preserving line boundaries."""
    text = text.replace("\x00", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -*•|:\t\r\n")


def extract_email(text: str) -> str:
    match = re.search(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b", text)
    return match.group(0) if match else ""


def extract_phone(text: str) -> str:
    pattern = re.compile(
        r"(?<!\d)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?"
        r"\d{3,5}[\s.-]?\d{4}(?!\d)"
    )
    for match in pattern.finditer(text):
        candidate = match.group(0).strip()
        digits = re.sub(r"\D", "", candidate)
        if 10 <= len(digits) <= 15 and not looks_like_year_range(candidate):
            return candidate
    return ""


def looks_like_year_range(value: str) -> bool:
    return bool(re.fullmatch(r"\s*(19|20)\d{2}\s*[-/]\s*(19|20)\d{2}\s*", value))


def extract_full_name(text: str) -> str:
    """Infer the candidate name from the first resume header lines."""
    ignored = {
        "resume", "curriculum vitae", "cv", "profile", "summary", "contact",
        "email", "phone", "linkedin", "github", "portfolio",
    }

    for raw_line in text.splitlines()[:12]:
        line = clean_line(raw_line)
        lowered = line.lower()
        if not line or lowered in ignored:
            continue
        if "@" in line or re.search(r"\d{3,}", line):
            continue
        if any(token in lowered for token in ("http", "www.", "linkedin", "github")):
            continue

        words = [word.strip(".") for word in line.split()]
        alpha_words = [word for word in words if re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", word)]
        if 2 <= len(alpha_words) <= 4 and len(alpha_words) == len(words):
            title_case_ratio = sum(word[:1].isupper() for word in alpha_words) / len(alpha_words)
            if title_case_ratio >= 0.75 or line.isupper():
                return " ".join(word.title() if line.isupper() else word for word in alpha_words)
    return ""


def extract_sections(text: str) -> dict[str, list[str]]:
    """Group lines under common resume section headers."""
    sections: dict[str, list[str]] = {key: [] for key in SECTION_HEADERS}
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = clean_line(raw_line)
        if not line:
            continue

        header_key = detect_section_header(line)
        if header_key:
            current_key = header_key
            continue

        if current_key:
            sections[current_key].append(line)

    return sections


def detect_section_header(line: str) -> str | None:
    lowered = line.lower().strip(":")
    if len(lowered) > 45:
        return None
    for key, aliases in SECTION_HEADERS.items():
        if lowered in aliases:
            return key
    return None


def unique_lines(lines: list[str], max_items: int = 8) -> list[str]:
    seen: set[str] = set()
    results: list[str] = []
    for line in lines:
        cleaned = clean_line(line)
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            results.append(cleaned)
        if len(results) >= max_items:
            break
    return results


def extract_skills(text: str, sections: dict[str, list[str]]) -> list[str]:
    search_space = "\n".join(sections.get("skills") or []) or text
    matched = []
    for skill in SKILLS_DB:
        escaped = re.escape(skill).replace(r"\ ", r"[\s/+.-]*")
        pattern = rf"(?<![\w+#]){escaped}(?![\w+#])"
        if re.search(pattern, search_space, re.IGNORECASE) or re.search(pattern, text, re.IGNORECASE):
            matched.append(skill)
    return sorted(set(matched), key=str.lower)


def extract_by_hints(text: str, section_lines: list[str], hints: tuple[str, ...], max_items: int = 8) -> list[str]:
    candidates = list(section_lines)
    for line in text.splitlines():
        cleaned = clean_line(line)
        lowered = cleaned.lower()
        if any(hint in lowered for hint in hints):
            candidates.append(cleaned)
    return unique_lines(candidates, max_items=max_items)


def calculate_score(parsed: dict) -> dict:
    contact_score = 10 if parsed["email"] and parsed["phone"] else 5 if parsed["email"] or parsed["phone"] else 0
    skills_score = min(len(parsed["skills"]) * 4, 30)
    education_score = 20 if parsed["education"] else 0
    experience_score = min(len(parsed["experience"]) * 7, 30)
    certification_score = 10 if parsed["certifications"] else 0
    total = min(contact_score + skills_score + education_score + experience_score + certification_score, 100)
    return {
        "total": total,
        "breakdown": {
            "contact": contact_score,
            "skills": skills_score,
            "education": education_score,
            "experience": experience_score,
            "certifications": certification_score,
        },
    }


def build_recommendations(parsed: dict) -> list[str]:
    suggestions = []
    if not parsed["full_name"]:
        suggestions.append("Place your full name clearly at the top of the resume.")
    if not parsed["email"] or not parsed["phone"]:
        suggestions.append("Add both email and phone number in the header for easy recruiter contact.")
    if len(parsed["skills"]) < 6:
        suggestions.append("Add a targeted skills section with tools and technologies from the job description.")
    if not parsed["education"]:
        suggestions.append("Include education with degree, institution, graduation year, and relevant honors.")
    if len(parsed["experience"]) < 2:
        suggestions.append("Expand experience bullets with measurable outcomes, ownership, and business impact.")
    if not parsed["certifications"]:
        suggestions.append("List relevant certifications, courses, or training when they strengthen the role fit.")
    if parsed["score"]["total"] >= 80:
        suggestions.append("Strong structure detected. Tailor keywords for each job posting to improve match quality.")
    return suggestions


def classify_candidate(score: int) -> str:
    if score >= 80:
        return "Strong match"
    if score >= 60:
        return "Good match"
    if score >= 40:
        return "Moderate match"
    return "Needs improvement"


def parse_resume(file_path: str | Path) -> dict:
    """Parse a PDF resume into structured JSON-compatible data."""
    text = extract_text_from_pdf(file_path)
    sections = extract_sections(text)

    parsed = {
        "full_name": extract_full_name(text),
        "email": extract_email(text),
        "phone": extract_phone(text),
        "skills": extract_skills(text, sections),
        "education": extract_by_hints(text, sections["education"], EDUCATION_HINTS),
        "experience": extract_by_hints(text, sections["experience"], EXPERIENCE_HINTS, max_items=10),
        "certifications": extract_by_hints(text, sections["certifications"], CERTIFICATION_HINTS),
        "raw_text_preview": text[:1200],
    }
    parsed["score"] = calculate_score(parsed)
    parsed["ranking_label"] = classify_candidate(parsed["score"]["total"])
    parsed["recommendations"] = build_recommendations(parsed)
    return parsed
