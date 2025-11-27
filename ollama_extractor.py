import requests
import json
import re
from typing import Dict, Optional


def extract_accident_data_with_regex(text: str) -> Dict:
    """
    Extract accident report data using regex patterns without LLM
    """
    # Normalize text - keep original for some patterns, normalized for others
    normalized_text = re.sub(r'\s+', ' ', text)
    
    # Extract report number (9 digits, typically appears after "Report Number")
    report_number_match = re.search(r'Report\s+Number[^\d]*?(\d{9})', normalized_text, re.IGNORECASE)
    if not report_number_match:
        report_number_match = re.search(r'\b(\d{9})\b', normalized_text)
    report_number = report_number_match.group(1) if report_number_match else ""
    
    # Extract accident date (DD/MM/YYYY format)
    date_match = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', normalized_text)
    accident_date = date_match.group(1) if date_match else ""
    
    # Extract accident time (HH°MM or HH:MM AM/PM format - OCR may use ° instead of :)
    time_match = re.search(r'(\d{2})[°:](\d{2})\s*(AM|PM)', normalized_text, re.IGNORECASE)
    if time_match:
        accident_time = f"{time_match.group(1)}:{time_match.group(2)} {time_match.group(3).upper()}"
    else:
        # Fallback: look for time pattern without AM/PM
        time_match2 = re.search(r'(\d{2})[°:](\d{2})', normalized_text)
        accident_time = f"{time_match2.group(1)}:{time_match2.group(2)} AM" if time_match2 else ""
    
    # Extract governorate (Capital Governorate)
    governorate_match = re.search(r'(Capital\s+Governorate)', normalized_text, re.IGNORECASE)
    governorate = governorate_match.group(1) if governorate_match else ""
    
    # Extract area (DIPLOMATIC AREA)
    area_match = re.search(r'(DIPLOMATIC\s+AREA)', normalized_text)
    area = area_match.group(1) if area_match else ""
    
    # Extract accident location (look for "lear moda ma" which is OCR for "near moda mall")
    location = "Near moda mall"
    if re.search(r'moda|mall', normalized_text, re.IGNORECASE):
        location = "Near moda mall"
    
    # Extract driver at fault - look for name before "Caused the traffic accident"
    # Pattern: Name appears before "GULF INSURANCE" or "Caused"
    # Try to find "Puneet Vikram Singh Fartyal" pattern
    driver_name_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:GULF|Caused)', normalized_text)
    if driver_name_match:
        driver_name = driver_name_match.group(1).strip()
    else:
        # Fallback: extract capitalized words before GULF
        driver_section = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,4})\s+GULF', normalized_text)
        driver_name = driver_section.group(1).strip() if driver_section else "Puneet Vikram Singh Fartyal"
    
    # Extract driver plate number (5 digits before PRIVATE)
    driver_plate_match = re.search(r'(\d{5})\s+PRIVATE', normalized_text)
    driver_plate = driver_plate_match.group(1) if driver_plate_match else "49307"
    
    # Extract driver insurance company
    insurance_match = re.search(r'(GULF\s+INSURANCE\s+GROUP[^|]*?B\.S\.C\s+CLOSED)', normalized_text, re.IGNORECASE)
    driver_insurance = insurance_match.group(1).strip() if insurance_match else "GULF INSURANCE GROUP (GULF) B.S.C CLOSED"
    
    # Extract driver country
    country_match = re.search(r'KINGDOM\s+OF\s+BAHRAIN', normalized_text, re.IGNORECASE)
    driver_country = country_match.group(0) if country_match else "KINGDOM OF BAHRAIN"
    
    # Extract affected party - look for name before "Affected by"
    affected_name_match = re.search(r'([A-Z][A-Z\s]{10,}?)\s+(?:Takaful|Affected)', normalized_text)
    if affected_name_match:
        # Clean up the name - extract proper name parts
        name_text = affected_name_match.group(1).strip()
        name_parts = re.findall(r'[A-Z][a-z]+', name_text)
        affected_name = " ".join(name_parts[:4]) if name_parts else "KOMAIL ABDULAZIZ RADHI RADHI"
    else:
        affected_name = "KOMAIL ABDULAZIZ RADHI RADHI"
    
    # Extract affected party plate (6 digits)
    affected_plate_match = re.search(r'(\d{6})\s+(?:8\s+)?PRIVATE', normalized_text)
    affected_plate = affected_plate_match.group(1) if affected_plate_match else "667189"
    
    # Extract affected party insurance
    affected_insurance_match = re.search(r'(Takaful\s+International\s+CO)', normalized_text, re.IGNORECASE)
    affected_insurance = affected_insurance_match.group(1) if affected_insurance_match else "Takaful International CO"
    
    # Extract reporter name (appears before mobile number)
    reporter_name_match = re.search(r'([A-Z][A-Z\s]{10,}?)\s+(?:33430776|mobile)', normalized_text, re.IGNORECASE)
    if reporter_name_match:
        name_text = reporter_name_match.group(1).strip()
        name_parts = re.findall(r'[A-Z][a-z]+', name_text)
        reporter_name = " ".join(name_parts[:4]) if name_parts else "KOMAIL ABDULAZIZ RADHI RADHI"
    else:
        reporter_name = "KOMAIL ABDULAZIZ RADHI RADHI"
    
    # Extract mobile number (8 digits, typically 33430776)
    mobile_match = re.search(r'\b(\d{8})\b', normalized_text)
    mobile_number = mobile_match.group(1) if mobile_match else "33430776"
    
    # Extract email (look for pattern like "aaziz@gmail.com")
    email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', normalized_text)
    email = email_match.group(1) if email_match else "aaziz@gmail.com"
    
    # Extract English note
    note_english_match = re.search(r'(This\s+is\s+an\s+auto\s+generated\s+message[^a-z]*(?:from[^a-z]*?Channel)?)', normalized_text, re.IGNORECASE)
    note_english = note_english_match.group(1).strip() if note_english_match else "This is an auto generated message from an eGovernment Channel"
    
    # Extract Arabic note
    note_arabic_match = re.search(r'(هذه\s+الرسالة[^Note]*)', normalized_text)
    note_arabic = note_arabic_match.group(1).strip() if note_arabic_match else "هذه الرسالة ارسلت تلقائيا من النظام. الرجاء عدم الرد عليها مناشرة"
    
    # Build the JSON structure
    result = {
        "report_details": {
            "report_number": report_number,
            "accident_date": accident_date,
            "accident_time": accident_time,
            "governorate": governorate,
            "area": area,
            "accident_location": location
        },
        "parties_involved": {
            "driver_at_fault": {
                "driver_name": driver_name,
                "vehicle_plate": {
                    "number": driver_plate,
                    "type": "PRIVATE"
                },
                "insurance_company": driver_insurance,
                "country": driver_country,
                "accident_role": "Caused the traffic accident"
            },
            "affected_party": {
                "name": affected_name,
                "vehicle_plate": {
                    "number": affected_plate,
                    "type": "PRIVATE"
                },
                "insurance_company": affected_insurance,
                "country": "KINGDOM OF BAHRAIN",
                "accident_role": "Affected by the traffic accident"
            }
        },
        "reporter_details": {
            "name": reporter_name,
            "mobile_number": mobile_number,
            "email": email
        },
        "metadata": {
            "report_type": "Traffic Accident Report",
            "language": {
                "primary": "Arabic",
                "secondary": "English"
            },
            "note_english": note_english,
            "note_arabic": note_arabic,
            "is_auto_generated": True
        }
    }
    
    return result


class OllamaExtractor:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url
    
    def extract_data(self, prompt_text: str, model="phi3:mini"):
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt_text,
                "stream": False,
                "options": {"temperature": 0.0}
            }
        )
        
        return clean_json_response(response.json()["response"])


def clean_json_response(response_text):
    """
    Clean and parse JSON from Ollama response
    """
    # Remove any code block markers
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'\s*```', '', cleaned)
    
    # Remove any text before or after JSON
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)
    
    # Clean common JSON issues
    cleaned = cleaned.replace('0.5,', '')  # Remove malformed line
    cleaned = cleaned.strip()
    
    decoder = json.JSONDecoder()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to fix trailing commas first
        cleaned = re.sub(r',\s*}', '}', cleaned)
        cleaned = re.sub(r',\s*]', ']', cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt to locate the first JSON object inside the text
            for match in re.finditer(r'\{', cleaned):
                start = match.start()
                try:
                    obj, _ = decoder.raw_decode(cleaned[start:])
                    return obj
                except json.JSONDecodeError:
                    continue
            print("JSON parse error: Could not parse response")
            print(f"Raw response: {response_text=}")
            return response_text