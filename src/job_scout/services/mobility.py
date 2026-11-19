"""Visa, relocation, citizenship and professional-registration flags."""

from __future__ import annotations

import re

from job_scout.models.job import MobilityFlags, RawJobRecord


SPONSOR_RE = (
    r"visa sponsorship (is )?(available|offered|provided)|will sponsor|sponsorship provided|"
    r"sponsorship (is )?available|(h-?1b|h1-b|tn|e-?3|o-?1) (visa )?sponsorship|"
    r"sponsor(ship of)? (an? )?(h-?1b|work visa|green card|permanent residen)|"
    r"open to (visa )?sponsorship|immigration sponsorship|green card sponsorship|"
    r"\bperm\b (labor certification|process|sponsorship)|\beb-?[23]\b"
)
NO_SPONSOR_RE = (
    r"no visa sponsorship|(cannot|can ?not|will not|won'?t|unable to|not able to|do(es)? not|don'?t) "
    r"(currently )?(provide |offer )?sponsor|sponsorship (is )?not (available|offered|provided)|"
    r"without (the need for )?(current or future )?(visa )?sponsorship|"
    r"not (eligible|available) for (visa )?sponsorship|no sponsorship"
)
GREEN_CARD_RE = r"green card|permanent residen|\bperm\b|\beb-?[23]\b"
US_PERSON_RE = (
    r"\bitar\b|u\.?s\.? persons?\b.{0,80}(22 cfr|export|itar|ear\b)|"
    r"must (be|qualify as) a u\.?s\.? person|(export control|ear/itar).{0,120}u\.?s\.? person"
)


def extract_mobility(title: str, description: str, raw: RawJobRecord) -> MobilityFlags:
    blob = f"{title}\n{description}".lower()
    flags = MobilityFlags(
        visa_sponsorship=raw.visa_sponsorship,
        relocation_assistance=raw.relocation_assistance,
        unknown=True,
    )
    notes: list[str] = []

    if flags.visa_sponsorship is None:
        # Negative statements first: "will not sponsor" contains "sponsor" too.
        if re.search(NO_SPONSOR_RE, blob):
            flags.visa_sponsorship = False
        elif re.search(SPONSOR_RE, blob):
            flags.visa_sponsorship = True
            if re.search(GREEN_CARD_RE, blob):
                notes.append("employment-based green card (EB-2/EB-3/PERM) sponsorship mentioned")
    if flags.relocation_assistance is None:
        if re.search(r"relocation (assistance|package|support)|will relocate", blob):
            flags.relocation_assistance = True
        elif re.search(r"no relocation", blob):
            flags.relocation_assistance = False

    if re.search(r"must be a (us|u\.s\.|united states|australian|eu) citizen|citizenship required", blob):
        flags.citizenship_required = True
        notes.append("explicit citizenship requirement")
    elif re.search(US_PERSON_RE, blob):
        # ITAR / EAR "U.S. person" roles cannot be filled by a visa applicant.
        flags.citizenship_required = True
        notes.append("ITAR/export-control: U.S. person required")
    if re.search(
        r"(must (already )?have|requires) (the right to work|unrestricted work (rights|authori[sz]ation)|"
        r"existing work (permit|visa|rights))",
        blob,
    ):
        flags.work_right_required = True
        notes.append("existing work-right required")
    if re.search(r"security clearance|nv1|nv2|sc cleared|secret clearance", blob):
        flags.security_clearance_required = True
        notes.append("security clearance required")
    if re.search(r"\b(pe license|p\.e\.|chartered engineer|ecsa|preng|cpeng)\b", blob):
        flags.professional_registration_required = True
        notes.append("professional registration mentioned")

    flags.unknown = all(
        value is None
        for value in (
            flags.visa_sponsorship,
            flags.relocation_assistance,
            flags.work_right_required,
            flags.citizenship_required,
        )
    )
    if flags.unknown:
        notes.append("visa/work-authorisation status unknown — not inferred")
    flags.work_authorisation_notes = "; ".join(notes) if notes else None
    return flags
