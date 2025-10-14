from typing import List, Dict

def build_suggestion_prompt(items: List[Dict], sub_grid: str, procedure_type: str = None) -> str:
    """
    Builds a structured prompt for Gemini to generate cost-effective alternatives.
    """
    
    context = f"""You are a medical supply cost optimization expert analyzing a Surgical Preference Card (SPC) for {procedure_type or 'a surgical procedure'}.

Your task: For each item listed below, suggest 3 cost-effective alternative products that:
1. Serve the same clinical purpose
2. Are commonly available from major medical suppliers
3. Cost less than the current item
4. Maintain equivalent quality and safety standards

IMPORTANT RULES:
- Return ONLY valid JSON, no markdown, no explanations outside JSON
- For items never used (lastUsed = "never" or null), set removalSuggestion.recommended = true
- Calculate cost savings accurately: costSavings = currentCost - estimatedCost
- Confidence score reflects: availability (0.3), cost accuracy (0.3), clinical equivalence (0.4)
- If no suitable alternatives exist, return empty suggestions array []
- Do not hallucinate product names - use realistic medical supply names

ITEM CATEGORY: {sub_grid}
"""

    items_json = "[\n"
    for idx, item in enumerate(items):
        items_json += f"""  {{
    "itemId": "{item['itemId']}",
    "name": "{item['name']}",
    "currentCost": {item['currentCost']},
    "lastUsed": {f'"{item["lastUsed"]}"' if item.get('lastUsed') else 'null'},
    "catalogNo": {f'"{item.get("catalogNo", "")}"' if item.get('catalogNo') else 'null'}
  }}{',' if idx < len(items) - 1 else ''}
"""
    items_json += "]"

    schema = """{
  "items": [
    {
      "itemId": "string",
      "name": "string",
      "currentCost": number,
      "neverUsedFlag": boolean,
      "suggestions": [
        {
          "name": "string (realistic product name)",
          "estimatedCost": number (must be < currentCost),
          "confidence": number (0-1),
          "rationale": "string (max 100 chars)"
        }
      ],
      "removalSuggestion": {
        "recommended": boolean (true if never used),
        "reason": "string or null"
      }
    }
  ]
}"""

    return f"""{context}

ITEMS TO ANALYZE:
{items_json}

REQUIRED OUTPUT SCHEMA:
{schema}

Generate suggestions now in valid JSON format:"""


def build_summary_prompt(analysis_results: List[Dict]) -> str:
    """
    Generates a human-readable summary after analysis.
    """
    total_items = len(analysis_results)
    items_with_suggestions = sum(1 for item in analysis_results if item.get('suggestions'))
    removal_candidates = sum(1 for item in analysis_results if item.get('neverUsedFlag'))
    
    total_potential_savings = sum(
        max([s['costSavings'] for s in item['suggestions']], default=0)
        for item in analysis_results if item.get('suggestions')
    )
    
    return f"""Analyzed {total_items} items. Found cost-saving alternatives for {items_with_suggestions} items with potential savings of ${total_potential_savings:.2f}. Identified {removal_candidates} never-used items recommended for removal."""