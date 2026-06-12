#!/usr/bin/env python3  
"""  
FHIR R4 Test Data Generator for MongoDB POC  
Generates ~10,000 resources per patient across 1,000 patients  
Output: NDJSON files ready for bulk MongoDB ingestion  
"""  
  
import json  
import random  
import uuid  
from datetime import datetime, timedelta, date  
from pathlib import Path  
from typing import Optional  
from enum import Enum  
  
from pydantic import BaseModel, Field  
from faker import Faker  
from tqdm import tqdm  
  
# Initialize Faker for realistic data  
fake = Faker()  
Faker.seed(42)  
random.seed(42)  
  
# =============================================================================  
# FHIR R4 Pydantic Models  
# =============================================================================  
  
class Reference(BaseModel):  
    """FHIR Reference type"""  
    reference: str  
    display: Optional[str] = None  
  
class Coding(BaseModel):  
    """FHIR Coding type"""  
    system: str  
    code: str  
    display: str  
  
class CodeableConcept(BaseModel):  
    """FHIR CodeableConcept type"""  
    coding: list[Coding]  
    text: Optional[str] = None  
  
class Identifier(BaseModel):  
    """FHIR Identifier type"""  
    system: str  
    value: str  
  
class HumanName(BaseModel):  
    """FHIR HumanName type"""  
    use: str = "official"  
    family: str  
    given: list[str]  
  
class Address(BaseModel):  
    """FHIR Address type"""  
    use: str = "home"  
    line: list[str]  
    city: str  
    state: str  
    postalCode: str  
    country: str = "US"  
  
class ContactPoint(BaseModel):  
    """FHIR ContactPoint type"""  
    system: str  
    value: str  
    use: str  
  
class Period(BaseModel):  
    """FHIR Period type"""  
    start: str  
    end: Optional[str] = None  
  
class Quantity(BaseModel):  
    """FHIR Quantity type"""  
    value: float  
    unit: str  
    system: str = "http://unitsofmeasure.org"  
    code: str  
  
# =============================================================================  
# FHIR Resources  
# =============================================================================  
  
class Patient(BaseModel):  
    """FHIR Patient Resource"""  
    resourceType: str = "Patient"  
    id: str  
    identifier: list[Identifier]  
    name: list[HumanName]  
    gender: str  
    birthDate: str  
    address: list[Address]  
    telecom: list[ContactPoint]  
    maritalStatus: Optional[CodeableConcept] = None  
  
class Practitioner(BaseModel):  
    """FHIR Practitioner Resource"""  
    resourceType: str = "Practitioner"  
    id: str  
    identifier: list[Identifier]  
    name: list[HumanName]  
    gender: str  
    telecom: list[ContactPoint]  
  
class Organization(BaseModel):  
    """FHIR Organization Resource"""  
    resourceType: str = "Organization"  
    id: str  
    identifier: list[Identifier]  
    name: str  
    type: list[CodeableConcept]  
    address: list[Address]  
    telecom: list[ContactPoint]  
  
class Encounter(BaseModel):  
    """FHIR Encounter Resource"""  
    resourceType: str = "Encounter"  
    id: str  
    status: str  
    class_: Coding = Field(..., alias="class")  
    type: list[CodeableConcept]  
    subject: Reference  
    participant: list[dict]  
    period: Period  
    serviceProvider: Optional[Reference] = None  
      
    class Config:  
        populate_by_name = True  
  
class Condition(BaseModel):  
    """FHIR Condition Resource"""  
    resourceType: str = "Condition"  
    id: str  
    clinicalStatus: CodeableConcept  
    verificationStatus: CodeableConcept  
    category: list[CodeableConcept]  
    code: CodeableConcept  
    subject: Reference  
    encounter: Optional[Reference] = None  
    onsetDateTime: Optional[str] = None  
    recordedDate: str  
  
class Observation(BaseModel):  
    """FHIR Observation Resource"""  
    resourceType: str = "Observation"  
    id: str  
    status: str  
    category: list[CodeableConcept]  
    code: CodeableConcept  
    subject: Reference  
    encounter: Optional[Reference] = None  
    effectiveDateTime: str  
    valueQuantity: Optional[Quantity] = None  
    valueCodeableConcept: Optional[CodeableConcept] = None  
  
class MedicationRequest(BaseModel):  
    """FHIR MedicationRequest Resource"""  
    resourceType: str = "MedicationRequest"  
    id: str  
    status: str  
    intent: str  
    medicationCodeableConcept: CodeableConcept  
    subject: Reference  
    encounter: Optional[Reference] = None  
    authoredOn: str  
    requester: Optional[Reference] = None  
    dosageInstruction: list[dict]  
  
class Procedure(BaseModel):  
    """FHIR Procedure Resource"""  
    resourceType: str = "Procedure"  
    id: str  
    status: str  
    code: CodeableConcept  
    subject: Reference  
    encounter: Optional[Reference] = None  
    performedDateTime: Optional[str] = None  
    performer: list[dict]  
  
class DiagnosticReport(BaseModel):  
    """FHIR DiagnosticReport Resource"""  
    resourceType: str = "DiagnosticReport"  
    id: str  
    status: str  
    category: list[CodeableConcept]  
    code: CodeableConcept  
    subject: Reference  
    encounter: Optional[Reference] = None  
    effectiveDateTime: str  
    issued: str  
    result: list[Reference]  
  
class AllergyIntolerance(BaseModel):  
    """FHIR AllergyIntolerance Resource"""  
    resourceType: str = "AllergyIntolerance"  
    id: str  
    clinicalStatus: CodeableConcept  
    verificationStatus: CodeableConcept  
    type: str  
    category: list[str]  
    criticality: str  
    code: CodeableConcept  
    patient: Reference  
    recordedDate: str  
  
class Immunization(BaseModel):  
    """FHIR Immunization Resource"""  
    resourceType: str = "Immunization"  
    id: str  
    status: str  
    vaccineCode: CodeableConcept  
    patient: Reference  
    encounter: Optional[Reference] = None  
    occurrenceDateTime: str  
    primarySource: bool  
  
class CarePlan(BaseModel):  
    """FHIR CarePlan Resource"""  
    resourceType: str = "CarePlan"  
    id: str  
    status: str  
    intent: str  
    category: list[CodeableConcept]  
    subject: Reference  
    encounter: Optional[Reference] = None  
    period: Period  
    activity: list[dict]  
  
class DocumentReference(BaseModel):  
    """FHIR DocumentReference Resource"""  
    resourceType: str = "DocumentReference"  
    id: str  
    status: str  
    type: CodeableConcept  
    subject: Reference  
    date: str  
    author: list[Reference]  
    content: list[dict]  
    context: Optional[dict] = None  
  
# =============================================================================  
# Reference Data (Code Systems)  
# =============================================================================  
  
ENCOUNTER_TYPES = [  
    ("AMB", "ambulatory", "Ambulatory"),  
    ("EMER", "emergency", "Emergency"),  
    ("IMP", "inpatient encounter", "Inpatient"),  
    ("OBSENC", "observation encounter", "Observation"),  
]  
  
CONDITION_CODES = [  
    ("38341003", "Hypertension", "http://snomed.info/sct"),  
    ("44054006", "Type 2 Diabetes", "http://snomed.info/sct"),  
    ("195967001", "Asthma", "http://snomed.info/sct"),  
    ("13645005", "COPD", "http://snomed.info/sct"),  
    ("84114007", "Heart Failure", "http://snomed.info/sct"),  
    ("73211009", "Diabetes Mellitus", "http://snomed.info/sct"),  
    ("59621000", "Essential Hypertension", "http://snomed.info/sct"),  
    ("40930008", "Hypothyroidism", "http://snomed.info/sct"),  
    ("35489007", "Depression", "http://snomed.info/sct"),  
    ("69896004", "Rheumatoid Arthritis", "http://snomed.info/sct"),  
]  
  
VITAL_SIGNS = [  
    ("8867-4", "Heart rate", "beats/min", "/min", 60, 100),  
    ("8480-6", "Systolic BP", "mmHg", "mm[Hg]", 90, 140),  
    ("8462-4", "Diastolic BP", "mmHg", "mm[Hg]", 60, 90),  
    ("8310-5", "Body temperature", "°C", "Cel", 36.1, 37.2),  
    ("9279-1", "Respiratory rate", "breaths/min", "/min", 12, 20),  
    ("29463-7", "Body weight", "kg", "kg", 50, 120),  
    ("8302-2", "Body height", "cm", "cm", 150, 200),  
    ("39156-5", "BMI", "kg/m²", "kg/m2", 18.5, 35),  
    ("59408-5", "Oxygen saturation", "%", "%", 94, 100),  
]  
  
LAB_TESTS = [  
    ("2339-0", "Glucose", "mg/dL", "mg/dL", 70, 140),  
    ("2160-0", "Creatinine", "mg/dL", "mg/dL", 0.7, 1.3),  
    ("17861-6", "Calcium", "mg/dL", "mg/dL", 8.5, 10.5),  
    ("2951-2", "Sodium", "mmol/L", "mmol/L", 136, 145),  
    ("2823-3", "Potassium", "mmol/L", "mmol/L", 3.5, 5.0),  
    ("718-7", "Hemoglobin", "g/dL", "g/dL", 12, 17),  
    ("4544-3", "Hematocrit", "%", "%", 36, 50),  
    ("6690-2", "WBC", "10*3/uL", "10*3/uL", 4, 11),  
    ("777-3", "Platelets", "10*3/uL", "10*3/uL", 150, 400),  
    ("2085-9", "HDL Cholesterol", "mg/dL", "mg/dL", 40, 80),  
    ("2089-1", "LDL Cholesterol", "mg/dL", "mg/dL", 70, 160),  
    ("2093-3", "Total Cholesterol", "mg/dL", "mg/dL", 150, 240),  
    ("4548-4", "HbA1c", "%", "%", 4.5, 8.0),  
]  
  
MEDICATIONS = [  
    ("314076", "Lisinopril 10 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("197361", "Metformin 500 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("310965", "Atorvastatin 20 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("197379", "Amlodipine 5 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("310798", "Omeprazole 20 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("312961", "Levothyroxine 50 MCG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("197591", "Hydrochlorothiazide 25 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("617312", "Metoprolol 50 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("859751", "Acetaminophen 500 MG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
    ("197517", "Albuterol 90 MCG", "http://www.nlm.nih.gov/research/umls/rxnorm"),  
]  
  
PROCEDURES = [  
    ("268400002", "12 lead ECG", "http://snomed.info/sct"),  
    ("167995008", "Chest X-ray", "http://snomed.info/sct"),  
    ("252416005", "Colonoscopy", "http://snomed.info/sct"),  
    ("73761001", "CT of head", "http://snomed.info/sct"),  
    ("77477000", "CT of abdomen", "http://snomed.info/sct"),  
    ("241615005", "MRI of brain", "http://snomed.info/sct"),  
    ("40701008", "Echocardiogram", "http://snomed.info/sct"),  
    ("28163009", "Skin biopsy", "http://snomed.info/sct"),  
    ("5880005", "Physical examination", "http://snomed.info/sct"),  
    ("225385008", "Blood draw", "http://snomed.info/sct"),  
]  
  
ALLERGIES = [  
    ("387458008", "Aspirin", "medication"),  
    ("372687004", "Amoxicillin", "medication"),  
    ("91936005", "Penicillin", "medication"),  
    ("387517004", "Ibuprofen", "medication"),  
    ("227493005", "Peanuts", "food"),  
    ("102263004", "Eggs", "food"),  
    ("3718001", "Cow's milk", "food"),  
    ("256349002", "Shellfish", "food"),  
    ("256277009", "Grass pollen", "environment"),  
    ("256417003", "Horse dander", "environment"),  
]  
  
VACCINES = [  
    ("08", "Hepatitis B", "http://hl7.org/fhir/sid/cvx"),  
    ("03", "MMR", "http://hl7.org/fhir/sid/cvx"),  
    ("21", "Varicella", "http://hl7.org/fhir/sid/cvx"),  
    ("115", "Tdap", "http://hl7.org/fhir/sid/cvx"),  
    ("140", "Influenza", "http://hl7.org/fhir/sid/cvx"),  
    ("207", "COVID-19 Moderna", "http://hl7.org/fhir/sid/cvx"),  
    ("208", "COVID-19 Pfizer", "http://hl7.org/fhir/sid/cvx"),  
    ("33", "Pneumococcal", "http://hl7.org/fhir/sid/cvx"),  
    ("52", "Hepatitis A", "http://hl7.org/fhir/sid/cvx"),  
    ("121", "Zoster", "http://hl7.org/fhir/sid/cvx"),  
]  
  
# =============================================================================
# Clinical Note Templates
# =============================================================================
# Templates mix expanded clinical terms with abbreviations on purpose so that
# Atlas Search synonym mappings (clinical_synonyms) and Vector Search both
# return meaningful hits. Each template is keyed off a condition the encounter
# carries; a generic template is used as a fallback.

NOTE_TEMPLATES: dict[str, list[str]] = {
    "Hypertension": [
        "CC: Follow-up for HTN. HPI: {age}yo with longstanding hypertension, "
        "home BP averaging 148/92. Denies chest pain or SOB. "
        "A/P: Essential hypertension, suboptimal control. Increase lisinopril "
        "to 20 mg daily, continue HCTZ, recheck BP in 4 weeks. Lifestyle "
        "counseling on low-sodium diet and aerobic activity.",
        "Patient presents for routine BP check. HTN diagnosed 6 years ago. "
        "Current meds: amlodipine 10 mg, losartan 50 mg. BP today 138/86, HR 74. "
        "Plan: continue current antihypertensive regimen, basic metabolic panel, "
        "fasting lipid panel including LDL and HDL.",
    ],
    "Essential Hypertension": [
        "Established patient with essential hypertension, on dual therapy. "
        "BP 144/90, HR 78 regular. No headache, no blurred vision, no chest pain. "
        "A: HTN, stage 1, uncontrolled. P: add chlorthalidone 12.5 mg daily, "
        "monitor electrolytes, follow-up in 6 weeks.",
    ],
    "Type 2 Diabetes": [
        "T2DM follow-up. HbA1c 8.2 (up from 7.4). FBG averaging 180. "
        "Reports polyuria and fatigue, denies DKA symptoms. Compliant with "
        "metformin 1000 mg BID. A/P: type 2 diabetes mellitus, poorly "
        "controlled. Start empagliflozin 10 mg daily, dietitian referral, "
        "repeat A1c in 3 months. Foot exam unremarkable.",
        "Patient with T2DM x 8 years. HbA1c 7.1, improved from 7.8. "
        "Continues metformin and semaglutide. No hypoglycemic events. "
        "Annual diabetic eye exam scheduled. Plan: continue current regimen, "
        "monitor blood glucose, recheck hemoglobin A1c in 3 months.",
    ],
    "Diabetes Mellitus": [
        "DM follow-up visit. Patient with diabetes mellitus on basal insulin. "
        "Fasting blood sugar 165, A1c 9.0. Discussed risk of DKA and HHS. "
        "Plan: titrate glargine, add prandial insulin, diabetic education, "
        "comprehensive metabolic panel and HbA1c in 6 weeks.",
    ],
    "Asthma": [
        "Asthma exacerbation. Patient reports wheezing, cough, and chest "
        "tightness over the past 3 days. Peak flow 60% of personal best. "
        "Albuterol use increased to q4h. SpO2 95% on room air. A/P: moderate "
        "asthma exacerbation. Start prednisone 40 mg daily x 5 days, continue "
        "ICS/LABA, follow-up in 1 week, PFT in 1 month.",
    ],
    "COPD": [
        "COPD follow-up. Patient with chronic obstructive pulmonary disease "
        "(GOLD stage III), former smoker. Reports increased SOB on exertion "
        "and chronic productive cough. SpO2 91% on room air. A/P: COPD with "
        "chronic bronchitis component. Continue tiotropium and ICS/LABA, "
        "pulmonary rehab referral, ABG and chest x-ray ordered.",
        "Chronic obstructive pulmonary disease, acute exacerbation. Increased "
        "dyspnea, productive cough with purulent sputum. ABG: pH 7.36, pCO2 48. "
        "P: azithromycin 5-day course, prednisone taper, supplemental O2 2L NC, "
        "smoking cessation counseling.",
    ],
    "Heart Failure": [
        "CHF exacerbation. Patient with HFrEF (EF 30%) presenting with worsening "
        "SOB, orthopnea, and bilateral lower extremity edema. JVD elevated. "
        "BNP 1850. A/P: acute on chronic heart failure. IV furosemide, daily "
        "weights, fluid restriction 1.5L, telemetry monitoring, ECG to evaluate "
        "for AFib, echocardiogram tomorrow.",
        "Congestive heart failure follow-up. Stable on guideline-directed medical "
        "therapy: carvedilol, lisinopril, spironolactone. No recent admissions. "
        "Weight stable. Plan: continue GDMT, BMP, repeat ECG, cardiology in 3 months.",
    ],
    "Hypothyroidism": [
        "Hypothyroidism follow-up. Patient on levothyroxine 75 mcg daily. "
        "Reports fatigue and cold intolerance. TSH 6.2 (elevated). "
        "A/P: hypothyroidism, undertreated. Increase levothyroxine to 88 mcg, "
        "recheck TSH and free T4 in 6 weeks.",
    ],
    "Depression": [
        "Depression follow-up. PHQ-9 score 14 (moderate). Patient on sertraline "
        "50 mg for 8 weeks with partial response. Denies SI/HI. Sleep poor, "
        "appetite decreased. A/P: major depressive disorder. Increase sertraline "
        "to 100 mg, continue therapy, follow-up in 4 weeks.",
    ],
    "Rheumatoid Arthritis": [
        "RA follow-up. Patient with seropositive rheumatoid arthritis on "
        "methotrexate and hydroxychloroquine. Morning stiffness 30 minutes, "
        "mild synovitis MCP joints. CDAI 8. Plan: continue current DMARDs, "
        "CBC, LFTs, follow-up in 3 months.",
    ],
}

GENERIC_NOTE_TEMPLATES = [
    "Patient presents for routine follow-up. Reviewed interim history. "
    "No new complaints. Vitals stable: BP within normal limits, HR regular, "
    "SpO2 98% on room air. Physical exam unremarkable. Plan: continue current "
    "medications, age-appropriate preventive screening, follow-up in 6 months.",
    "Annual wellness visit. Patient reports overall good health, exercising "
    "regularly, non-smoker. BP 122/76, HR 68. Lipid panel showed LDL 105, "
    "HDL 58. Plan: continue lifestyle measures, repeat labs in one year, "
    "vaccinations updated.",
    "ED visit for chest pain. ECG without acute ischemic changes, troponin "
    "negative x2. Symptoms resolved. Likely musculoskeletal etiology. "
    "Discharged with PCP follow-up, return precautions reviewed.",
    "Patient evaluated for SOB. Lungs clear bilaterally, no wheezing. SpO2 97% "
    "on room air. ECG normal sinus rhythm. Likely deconditioning. Plan: chest "
    "x-ray, BMP, pulmonary function test if symptoms persist.",
]


def _clinical_note(condition_names: list[str]) -> str:
    """Compose a short narrative referencing the encounter's conditions.

    Picks a template per condition (or a generic one if no match), joins them,
    and prepends a chief-complaint-style line. Output stays under ~800 chars
    so embeddings remain meaningful.
    """
    parts: list[str] = []
    for name in condition_names[:2]:
        templates = NOTE_TEMPLATES.get(name)
        if templates:
            parts.append(random.choice(templates).format(age=random.randint(35, 85)))
    if not parts:
        parts.append(random.choice(GENERIC_NOTE_TEMPLATES))
    return " ".join(parts)[:800]


# =============================================================================
# Data Generator Class
# =============================================================================

  
class FHIRDataGenerator:  
    """Generate realistic FHIR R4 test data"""  
      
    def __init__(self, output_dir: str = "fhir_data"):  
        self.output_dir = Path(output_dir)  
        self.output_dir.mkdir(exist_ok=True)  
          
        # Shared resources (practitioners, organizations)  
        self.practitioners: list[str] = []  
        self.organizations: list[str] = []  
          
    def generate_id(self) -> str:  
        """Generate a unique ID"""  
        return str(uuid.uuid4())  
      
    def random_date(self, start_year: int = 2020, end_year: int = 2024) -> str:  
        """Generate a random datetime string"""  
        start = datetime(start_year, 1, 1)  
        end = datetime(end_year, 12, 31)  
        delta = end - start  
        random_days = random.randint(0, delta.days)  
        dt = start + timedelta(days=random_days,   
                               hours=random.randint(0, 23),  
                               minutes=random.randint(0, 59))  
        return dt.isoformat() + "Z"  
      
    def random_birthdate(self, min_age: int = 18, max_age: int = 90) -> str:  
        """Generate a random birth date"""  
        today = date.today()  
        age = random.randint(min_age, max_age)  
        birth_year = today.year - age  
        birth_month = random.randint(1, 12)  
        birth_day = random.randint(1, 28)  
        return f"{birth_year}-{birth_month:02d}-{birth_day:02d}"  
      
    # -------------------------------------------------------------------------  
    # Resource Generators  
    # -------------------------------------------------------------------------  
      
    def generate_practitioner(self) -> Practitioner:  
        """Generate a Practitioner resource"""  
        prac_id = self.generate_id()  
        self.practitioners.append(prac_id)  
          
        return Practitioner(  
            id=prac_id,  
            identifier=[Identifier(  
                system="http://hl7.org/fhir/sid/us-npi",  
                value=fake.numerify("##########")  
            )],  
            name=[HumanName(  
                family=fake.last_name(),  
                given=[fake.first_name(), fake.first_name()[0]]  
            )],  
            gender=random.choice(["male", "female"]),  
            telecom=[ContactPoint(  
                system="phone",  
                value=fake.phone_number(),  
                use="work"  
            )]  
        )  
      
    def generate_organization(self) -> Organization:  
        """Generate an Organization resource"""  
        org_id = self.generate_id()  
        self.organizations.append(org_id)  
          
        return Organization(  
            id=org_id,  
            identifier=[Identifier(  
                system="http://hl7.org/fhir/sid/us-npi",  
                value=fake.numerify("##########")  
            )],  
            name=f"{fake.company()} Medical Center",  
            type=[CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/organization-type",  
                    code="prov",  
                    display="Healthcare Provider"  
                )]  
            )],  
            address=[Address(  
                line=[fake.street_address()],  
                city=fake.city(),  
                state=fake.state_abbr(),  
                postalCode=fake.zipcode()  
            )],  
            telecom=[ContactPoint(  
                system="phone",  
                value=fake.phone_number(),  
                use="work"  
            )]  
        )  
      
    def generate_patient(self, patient_id: str) -> Patient:  
        """Generate a Patient resource"""  
        gender = random.choice(["male", "female"])  
        first_name = fake.first_name_male() if gender == "male" else fake.first_name_female()  
          
        return Patient(  
            id=patient_id,  
            identifier=[  
                Identifier(  
                    system="http://hospital.org/mrn",  
                    value=fake.numerify("MRN-########")  
                ),  
                Identifier(  
                    system="http://hl7.org/fhir/sid/us-ssn",  
                    value=fake.ssn()  
                )  
            ],  
            name=[HumanName(  
                family=fake.last_name(),  
                given=[first_name, fake.first_name()[0]]  
            )],  
            gender=gender,  
            birthDate=self.random_birthdate(),  
            address=[Address(  
                line=[fake.street_address()],  
                city=fake.city(),  
                state=fake.state_abbr(),  
                postalCode=fake.zipcode()  
            )],  
            telecom=[  
                ContactPoint(system="phone", value=fake.phone_number(), use="home"),  
                ContactPoint(system="email", value=fake.email(), use="home")  
            ],  
            maritalStatus=CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",  
                    code=random.choice(["M", "S", "D", "W"]),  
                    display=random.choice(["Married", "Single", "Divorced", "Widowed"])  
                )]  
            )  
        )  
      
    def generate_encounter(self, patient_id: str, encounter_date: str) -> Encounter:  
        """Generate an Encounter resource"""  
        enc_type = random.choice(ENCOUNTER_TYPES)  
        duration_hours = random.randint(1, 72)  
          
        start_dt = datetime.fromisoformat(encounter_date.replace("Z", ""))  
        end_dt = start_dt + timedelta(hours=duration_hours)  
          
        return Encounter(  
            id=self.generate_id(),  
            status="finished",  
            **{"class": Coding(  
                system="http://terminology.hl7.org/CodeSystem/v3-ActCode",  
                code=enc_type[0],  
                display=enc_type[2]  
            )},  
            type=[CodeableConcept(  
                coding=[Coding(  
                    system="http://snomed.info/sct",  
                    code="308335008",  
                    display="Patient encounter procedure"  
                )],  
                text=enc_type[1]  
            )],  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            participant=[{  
                "type": [{  
                    "coding": [{  
                        "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",  
                        "code": "ATND",  
                        "display": "attender"  
                    }]  
                }],  
                "individual": {  
                    "reference": f"Practitioner/{random.choice(self.practitioners)}"  
                }  
            }],  
            period=Period(  
                start=encounter_date,  
                end=end_dt.isoformat() + "Z"  
            ),  
            serviceProvider=Reference(  
                reference=f"Organization/{random.choice(self.organizations)}"  
            ) if self.organizations else None  
        )  
      
    def generate_condition(self, patient_id: str, encounter_id: str) -> Condition:  
        """Generate a Condition resource"""  
        condition = random.choice(CONDITION_CODES)  
          
        return Condition(  
            id=self.generate_id(),  
            clinicalStatus=CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/condition-clinical",  
                    code="active",  
                    display="Active"  
                )]  
            ),  
            verificationStatus=CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/condition-ver-status",  
                    code="confirmed",  
                    display="Confirmed"  
                )]  
            ),  
            category=[CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/condition-category",  
                    code="encounter-diagnosis",  
                    display="Encounter Diagnosis"  
                )]  
            )],  
            code=CodeableConcept(  
                coding=[Coding(  
                    system=condition[2],  
                    code=condition[0],  
                    display=condition[1]  
                )],  
                text=condition[1]  
            ),  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            recordedDate=self.random_date()  
        )  
      
    def generate_vital_observation(self, patient_id: str, encounter_id: str,   
                                    obs_date: str) -> Observation:  
        """Generate a vital signs Observation"""  
        vital = random.choice(VITAL_SIGNS)  
        value = round(random.uniform(vital[4], vital[5]), 1)  
          
        return Observation(  
            id=self.generate_id(),  
            status="final",  
            category=[CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/observation-category",  
                    code="vital-signs",  
                    display="Vital Signs"  
                )]  
            )],  
            code=CodeableConcept(  
                coding=[Coding(  
                    system="http://loinc.org",  
                    code=vital[0],  
                    display=vital[1]  
                )],  
                text=vital[1]  
            ),  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            effectiveDateTime=obs_date,  
            valueQuantity=Quantity(  
                value=value,  
                unit=vital[2],  
                code=vital[3]  
            )  
        )  
      
    def generate_lab_observation(self, patient_id: str, encounter_id: str,  
                                  obs_date: str) -> Observation:  
        """Generate a laboratory Observation"""  
        lab = random.choice(LAB_TESTS)  
        value = round(random.uniform(lab[4], lab[5]), 2)  
          
        return Observation(  
            id=self.generate_id(),  
            status="final",  
            category=[CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/observation-category",  
                    code="laboratory",  
                    display="Laboratory"  
                )]  
            )],  
            code=CodeableConcept(  
                coding=[Coding(  
                    system="http://loinc.org",  
                    code=lab[0],  
                    display=lab[1]  
                )],  
                text=lab[1]  
            ),  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            effectiveDateTime=obs_date,  
            valueQuantity=Quantity(  
                value=value,  
                unit=lab[2],  
                code=lab[3]  
            )  
        )  
      
    def generate_medication_request(self, patient_id: str,   
                                     encounter_id: str) -> MedicationRequest:  
        """Generate a MedicationRequest resource"""  
        med = random.choice(MEDICATIONS)  
          
        return MedicationRequest(  
            id=self.generate_id(),  
            status="active",  
            intent="order",  
            medicationCodeableConcept=CodeableConcept(  
                coding=[Coding(  
                    system=med[2],  
                    code=med[0],  
                    display=med[1]  
                )],  
                text=med[1]  
            ),  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            authoredOn=self.random_date(),  
            requester=Reference(  
                reference=f"Practitioner/{random.choice(self.practitioners)}"  
            ),  
            dosageInstruction=[{  
                "text": f"Take {random.randint(1,2)} tablet(s) {random.choice(['once', 'twice', 'three times'])} daily",  
                "timing": {  
                    "repeat": {  
                        "frequency": random.randint(1, 3),  
                        "period": 1,  
                        "periodUnit": "d"  
                    }  
                }  
            }]  
        )  
      
    def generate_procedure(self, patient_id: str, encounter_id: str) -> Procedure:  
        """Generate a Procedure resource"""  
        proc = random.choice(PROCEDURES)  
          
        return Procedure(  
            id=self.generate_id(),  
            status="completed",  
            code=CodeableConcept(  
                coding=[Coding(  
                    system=proc[2],  
                    code=proc[0],  
                    display=proc[1]  
                )],  
                text=proc[1]  
            ),  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            performedDateTime=self.random_date(),  
            performer=[{  
                "actor": {  
                    "reference": f"Practitioner/{random.choice(self.practitioners)}"  
                }  
            }]  
        )  
      
    def generate_diagnostic_report(self, patient_id: str, encounter_id: str,  
                                    observation_ids: list[str]) -> DiagnosticReport:  
        """Generate a DiagnosticReport resource"""  
        return DiagnosticReport(  
            id=self.generate_id(),  
            status="final",  
            category=[CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/v2-0074",  
                    code="LAB",  
                    display="Laboratory"  
                )]  
            )],  
            code=CodeableConcept(  
                coding=[Coding(  
                    system="http://loinc.org",  
                    code="24323-8",  
                    display="Comprehensive metabolic panel"  
                )],  
                text="Comprehensive Metabolic Panel"  
            ),  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            effectiveDateTime=self.random_date(),  
            issued=self.random_date(),  
            result=[Reference(reference=f"Observation/{obs_id}")   
                   for obs_id in observation_ids[:5]]  
        )  
      
    def generate_allergy(self, patient_id: str) -> AllergyIntolerance:  
        """Generate an AllergyIntolerance resource"""  
        allergy = random.choice(ALLERGIES)  
          
        return AllergyIntolerance(  
            id=self.generate_id(),  
            clinicalStatus=CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",  
                    code="active",  
                    display="Active"  
                )]  
            ),  
            verificationStatus=CodeableConcept(  
                coding=[Coding(  
                    system="http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",  
                    code="confirmed",  
                    display="Confirmed"  
                )]  
            ),  
            type="allergy",  
            category=[allergy[2]],  
            criticality=random.choice(["low", "high", "unable-to-assess"]),  
            code=CodeableConcept(  
                coding=[Coding(  
                    system="http://snomed.info/sct",  
                    code=allergy[0],  
                    display=allergy[1]  
                )],  
                text=allergy[1]  
            ),  
            patient=Reference(reference=f"Patient/{patient_id}"),  
            recordedDate=self.random_date()  
        )  
      
    def generate_immunization(self, patient_id: str,   
                               encounter_id: str) -> Immunization:  
        """Generate an Immunization resource"""  
        vaccine = random.choice(VACCINES)  
          
        return Immunization(  
            id=self.generate_id(),  
            status="completed",  
            vaccineCode=CodeableConcept(  
                coding=[Coding(  
                    system=vaccine[2],  
                    code=vaccine[0],  
                    display=vaccine[1]  
                )],  
                text=vaccine[1]  
            ),  
            patient=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            occurrenceDateTime=self.random_date(),  
            primarySource=True  
        )  
      
    def generate_careplan(self, patient_id: str, encounter_id: str,  
                          condition_ids: list[str]) -> CarePlan:  
        """Generate a CarePlan resource"""  
        return CarePlan(  
            id=self.generate_id(),  
            status="active",  
            intent="plan",  
            category=[CodeableConcept(  
                coding=[Coding(  
                    system="http://hl7.org/fhir/us/core/CodeSystem/careplan-category",  
                    code="assess-plan",  
                    display="Assessment and Plan of Treatment"  
                )]  
            )],  
            subject=Reference(reference=f"Patient/{patient_id}"),  
            encounter=Reference(reference=f"Encounter/{encounter_id}"),  
            period=Period(  
                start=self.random_date(),  
                end=self.random_date(2025, 2026)  
            ),  
            activity=[{  
                "detail": {  
                    "status": "in-progress",  
                    "description": random.choice([  
                        "Monitor blood pressure daily",  
                        "Follow diabetic diet",  
                        "Exercise 30 minutes daily",  
                        "Take medications as prescribed",  
                        "Follow up in 3 months"  
                    ])  
                }  
            } for _ in range(random.randint(2, 5))]  
        )  
      
    def generate_document_reference(self, patient_id: str,
                                     encounter_id: str,
                                     condition_names: list[str] | None = None
                                     ) -> DocumentReference:
        """Generate a DocumentReference with a realistic clinical narrative."""
        return DocumentReference(
            id=self.generate_id(),
            status="current",
            type=CodeableConcept(
                coding=[Coding(
                    system="http://loinc.org",
                    code="34133-9",
                    display="Summary of episode note"
                )],
                text="Clinical Summary"
            ),
            subject=Reference(reference=f"Patient/{patient_id}"),
            date=self.random_date(),
            author=[Reference(
                reference=f"Practitioner/{random.choice(self.practitioners)}"
            )],
            content=[{
                "attachment": {
                    "contentType": "text/plain",
                    "data": _clinical_note(condition_names or [])
                }
            }],
            context={
                "encounter": [{"reference": f"Encounter/{encounter_id}"}]
            }
        )

      
    # -------------------------------------------------------------------------  
    # Main Generation Logic  
    # -------------------------------------------------------------------------  
      
    def generate_patient_data(self, patient_id: str) -> list[dict]:  
        """Generate all resources for a single patient (~10,000 resources)"""  
        resources = []  
          
        # Generate patient  
        patient = self.generate_patient(patient_id)  
        resources.append(patient.model_dump(by_alias=True, exclude_none=True))  
          
        # Generate allergies (2-5 per patient)  
        for _ in range(random.randint(2, 5)):  
            allergy = self.generate_allergy(patient_id)  
            resources.append(allergy.model_dump(by_alias=True, exclude_none=True))  
          
        # Generate encounters and related resources  
        # ~100 encounters per patient, each with many observations  
        num_encounters = random.randint(80, 120)  
          
        for _ in range(num_encounters):  
            encounter_date = self.random_date()  
            encounter = self.generate_encounter(patient_id, encounter_date)  
            encounter_id = encounter.id  
            resources.append(encounter.model_dump(by_alias=True, exclude_none=True))  
              
            # Conditions (1-3 per encounter)
            condition_ids = []
            condition_names: list[str] = []
            for _ in range(random.randint(1, 3)):
                condition = self.generate_condition(patient_id, encounter_id)
                condition_ids.append(condition.id)
                condition_names.append(condition.code.text)
                resources.append(condition.model_dump(by_alias=True, exclude_none=True))

              
            # Vital signs observations (5-10 per encounter)  
            for _ in range(random.randint(5, 10)):  
                obs = self.generate_vital_observation(patient_id, encounter_id, encounter_date)  
                resources.append(obs.model_dump(by_alias=True, exclude_none=True))  
              
            # Lab observations (10-30 per encounter)  
            lab_obs_ids = []  
            for _ in range(random.randint(10, 30)):  
                obs = self.generate_lab_observation(patient_id, encounter_id, encounter_date)  
                lab_obs_ids.append(obs.id)  
                resources.append(obs.model_dump(by_alias=True, exclude_none=True))  
              
            # Diagnostic reports (1-3 per encounter)  
            for _ in range(random.randint(1, 3)):  
                report = self.generate_diagnostic_report(patient_id, encounter_id, lab_obs_ids)  
                resources.append(report.model_dump(by_alias=True, exclude_none=True))  
              
            # Medications (1-5 per encounter)  
            for _ in range(random.randint(1, 5)):  
                med = self.generate_medication_request(patient_id, encounter_id)  
                resources.append(med.model_dump(by_alias=True, exclude_none=True))  
              
            # Procedures (0-3 per encounter)  
            for _ in range(random.randint(0, 3)):  
                proc = self.generate_procedure(patient_id, encounter_id)  
                resources.append(proc.model_dump(by_alias=True, exclude_none=True))  
              
            # Immunizations (0-2 per encounter)  
            for _ in range(random.randint(0, 2)):  
                imm = self.generate_immunization(patient_id, encounter_id)  
                resources.append(imm.model_dump(by_alias=True, exclude_none=True))  
              
            # Care plans (0-1 per encounter)  
            if random.random() > 0.7:  
                careplan = self.generate_careplan(patient_id, encounter_id, condition_ids)  
                resources.append(careplan.model_dump(by_alias=True, exclude_none=True))  
              
            # Document references (1-2 per encounter)
            for _ in range(random.randint(1, 2)):
                doc = self.generate_document_reference(patient_id, encounter_id,
                                                       condition_names)
                resources.append(doc.model_dump(by_alias=True, exclude_none=True))

          
        return resources  
      
    def generate_shared_resources(self, num_practitioners: int = 100,  
                                   num_organizations: int = 20) -> list[dict]:  
        """Generate practitioners and organizations"""  
        resources = []  
          
        print(f"Generating {num_practitioners} practitioners...")  
        for _ in range(num_practitioners):  
            prac = self.generate_practitioner()  
            resources.append(prac.model_dump(by_alias=True, exclude_none=True))  
          
        print(f"Generating {num_organizations} organizations...")  
        for _ in range(num_organizations):  
            org = self.generate_organization()  
            resources.append(org.model_dump(by_alias=True, exclude_none=True))  
          
        return resources  
      
    def write_ndjson(self, resources: list[dict], filename: str):  
        """Write resources to NDJSON file"""  
        filepath = self.output_dir / filename  
        with open(filepath, 'w') as f:  
            for resource in resources:  
                f.write(json.dumps(resource, separators=(',', ':')) + '\n')  
        return filepath  
      
    def generate_all(self, num_patients: int = 1000,   
                     patients_per_file: int = 100):  
        """Generate all FHIR data for the POC"""  
        print("=" * 60)  
        print("FHIR R4 Test Data Generator for MongoDB POC")  
        print("=" * 60)  
          
        # Generate shared resources first  
        shared_resources = self.generate_shared_resources()  
        shared_file = self.write_ndjson(shared_resources, "shared_resources.ndjson")  
        print(f"✓ Wrote {len(shared_resources)} shared resources to {shared_file}")  
          
        # Generate patient data in batches  
        total_resources = len(shared_resources)  
        file_count = 0  
          
        for batch_start in range(0, num_patients, patients_per_file):  
            batch_end = min(batch_start + patients_per_file, num_patients)  
            batch_resources = []  
              
            print(f"\nGenerating patients {batch_start + 1} to {batch_end}...")  
              
            for i in tqdm(range(batch_start, batch_end),   
                         desc=f"Batch {file_count + 1}"):  
                patient_id = self.generate_id()  
                patient_resources = self.generate_patient_data(patient_id)  
                batch_resources.extend(patient_resources)  
              
            # Write batch to file  
            filename = f"patients_{batch_start + 1:05d}_to_{batch_end:05d}.ndjson"  
            filepath = self.write_ndjson(batch_resources, filename)  
            total_resources += len(batch_resources)  
            file_count += 1  
              
            print(f"✓ Wrote {len(batch_resources):,} resources to {filepath}")  
          
        # Summary  
        print("\n" + "=" * 60)  
        print("GENERATION COMPLETE")  
        print("=" * 60)  
        print(f"Total patients: {num_patients:,}")  
        print(f"Total resources: {total_resources:,}")  
        print(f"Average resources per patient: {total_resources / num_patients:,.0f}")  
        print(f"Output files: {file_count + 1} NDJSON files in {self.output_dir}/")  
        print(f"Estimated total size: ~{(total_resources * 500) / (1024**3):.1f} GB")  
          
        return total_resources  
  
  
# =============================================================================  
# Main Entry Point  
# =============================================================================  
  
if __name__ == "__main__":  
    import argparse  
      
    parser = argparse.ArgumentParser(description="Generate FHIR test data for MongoDB POC")  
    parser.add_argument("--patients", type=int, default=1000,  
                       help="Number of patients to generate (default: 1000)")  
    parser.add_argument("--batch-size", type=int, default=100,  
                       help="Patients per NDJSON file (default: 100)")  
    parser.add_argument("--output", type=str, default="fhir_data",  
                       help="Output directory (default: fhir_data)")  
      
    args = parser.parse_args()  
      
    generator = FHIRDataGenerator(output_dir=args.output)  
    generator.generate_all(  
        num_patients=args.patients,  
        patients_per_file=args.batch_size  
    )  
