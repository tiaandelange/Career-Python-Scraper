from job_scout.services.dpsa_pdf import is_engineering_relevant, parse_single_osd_advert


DWS_SAMPLE = """
DEPARTMENT OF WATER AND SANITATION
CLOSING DATE: 11 September 2026
NOTE: Interested applicants must submit their applications via the online link https://erecruitment.dws.gov.za
BRANCH: INFRASTRUCTURE MANAGEMENT: HEAD OFFICE CD: WATER RESOURCES INFRASTRUCTURE
SALARY: R914 817 - R1 376 199 Per Annum (All-inclusive OSD salary package)
CENTRE: Pretoria Head Office
REQUIREMENTS: A Civil Engineering degree (B Eng / BSc Eng) qualification.
DUTIES: Conduct dam safety evaluations, monitoring and implementation of rehabilitation projects.
"""


def test_parse_single_osd_advert_dws_style():
    post = parse_single_osd_advert(
        DWS_SAMPLE,
        post_id="110926/05",
        title_hint="ENGINEER PRODUCTION GRADE A – C REF NO: 110926/05 (X2 POSTS)",
        source_pdf_url="https://www.dws.gov.za/vacancies/Vacancies2026/110926/110926-05.pdf",
        department_hint="DWS",
    )
    assert post is not None
    assert post.post_id == "110926/05"
    assert post.salary_text and "914 817" in post.salary_text
    assert post.centre and "Pretoria" in post.centre
    assert post.closing_date is not None


def test_engineering_relevance_for_dws_titles():
    assert is_engineering_relevant("CONTROL ENGINEERING TECHNOLOGIST GRADE A (CIVIL)", "")
    assert is_engineering_relevant("ENGINEER PRODUCTION GRADE A – C", "")
    assert not is_engineering_relevant("DRIVER / MESSENGER", "deliver documents")
