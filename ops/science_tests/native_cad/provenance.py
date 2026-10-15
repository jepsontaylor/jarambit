"""Report how a published sentence describes itself.

The class is not a verified measurement. A typed exact-subject case
certificate is required before any native measurement is verified, and
this lane does not hold that S08 contract.
"""

import re

REPORTED_DIRECT_UNVERIFIED = "reported_direct_unverified"
REPORTED_CARRIED_OR_RATIO = "reported_carried_or_ratio"
REPORTED_MISSING = "reported_missing"

_DONOR = re.compile(r"carry|ratio|record|\bg2\b|w80d", re.IGNORECASE)
_DESIGN = re.compile(
    r"\bc\s*\.?\s*(\d+)(?:\s*\.\s*(\d+))?\s*([a-z])?\b",
    re.IGNORECASE,
)
_NEGATED = re.compile(
    r"\b(?:not|no|never|non|without|isn'?t|aren'?t|wasn'?t|cannot|can't)"
    r"\s+(?:a\s+|an\s+|the\s+)?(?:direct\w*|b-rep)\b|\bindirect\b",
    re.IGNORECASE,
)
_DIRECT = re.compile(r"\bdirect|b-rep", re.IGNORECASE)


def _subject_token(subject):
    if not subject:
        return ""
    return re.sub(r"[^a-z0-9.]", "", subject.lower())


def _design_tokens(text):
    tokens = []
    for match in _DESIGN.finditer(text or ""):
        token = "c" + match.group(1)
        if match.group(2):
            token += "." + match.group(2)
        if match.group(3):
            token += match.group(3).lower()
        tokens.append(token)
    return tokens


def mentions_other_design(text, subject):
    """True when the sentence names a design other than the subject."""
    own = _subject_token(subject)
    if not own:
        return False
    return any(token != own for token in _design_tokens(text))


def reported_provenance(source_text, subject=None):
    """Classify a claim. Negation, another design, and silence stay unverified."""
    text = source_text or ""
    if not text.strip():
        return REPORTED_MISSING
    if _DONOR.search(text) or mentions_other_design(text, subject):
        return REPORTED_CARRIED_OR_RATIO
    residual = _NEGATED.sub(" ", text)
    if _DIRECT.search(residual):
        return REPORTED_DIRECT_UNVERIFIED
    return REPORTED_MISSING


def verified_native_measurement(source_text=None, certificate=None):
    """False until a typed exact-subject/case certificate exists.

    Source text and a bare asset hash do not verify a measurement.
    """
    del source_text, certificate
    return False


def provenance_class(source_text, subject=None):
    """Backward-compatible name for reported_provenance. Still unverified."""
    return reported_provenance(source_text, subject=subject)


def binding_status(genome_id=None, contract=None):
    """A nonempty genome id is not an S08 binding."""
    del genome_id, contract
    return "INCOMPLETE"
