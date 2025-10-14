import google.generativeai as genai
from app.config import get_settings
from app.prompts import build_suggestion_prompt
import json
import re
from typing import List, Dict
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
settings = get_settings()

# Configure Gemini
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Thread pool for running sync Gemini calls
executor = ThreadPoolExecutor(max_workers=5)

class GeminiService:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": settings.GEMINI_TEMPERATURE,
                "max_output_tokens": settings.GEMINI_MAX_TOKENS,
            }
        )
    
    async def generate_suggestions(
        self, 
        items: List[Dict], 
        sub_grid: str, 
        procedure_type: str = None
    ) -> Dict:
        """
        Calls Gemini API to generate suggestions for items.
        Runs the synchronous Gemini call in a thread pool to avoid blocking.
        """
        try:
            prompt = build_suggestion_prompt(items, sub_grid, procedure_type)
            
            logger.info(f"Calling Gemini for {len(items)} items in {sub_grid}")
            logger.info(f"Prompt length: {len(prompt)} characters")
            logger.debug(f"Prompt preview: {prompt[:300]}")
            
            # Run synchronous Gemini call in thread pool
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                executor,
                self._call_gemini_sync,
                prompt
            )
            
            # Check if response has content
            if not response.candidates or len(response.candidates) == 0:
                logger.error(f"Gemini returned no candidates. Finish reason: {response.prompt_feedback if hasattr(response, 'prompt_feedback') else 'unknown'}")
                raise ValueError("Gemini returned empty response - request may have been blocked by safety filters")
            
            candidate = response.candidates[0]
            logger.info(f"Candidate finish_reason: {candidate.finish_reason}")
            
            # Extract JSON from response
            if not candidate.content or not candidate.content.parts:
                logger.error("Gemini candidate has no content parts")
                raise ValueError("Gemini returned no content - request blocked by safety filters")
            
            raw_text = candidate.content.parts[0].text
            logger.info(f"Gemini response received (length: {len(raw_text)})")
            logger.debug(f"Raw response preview: {raw_text[:300]}")
            
            # Parse JSON with improved extraction
            result = self._extract_json(raw_text)
            
            logger.info("JSON parsing successful")
            
            # Validate and enrich response
            return self._process_gemini_response(result, items)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response: {e}")
            logger.error(f"Raw response: {raw_text[:500]}")
            raise ValueError(f"Gemini returned invalid JSON: {str(e)}")
        
        except Exception as e:
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise
    
    def _call_gemini_sync(self, prompt: str):
        """
        Synchronous wrapper for Gemini API call.
        This runs in a thread pool to avoid blocking the event loop.
        """
        try:
            response = self.model.generate_content(prompt)
            return response
        except Exception as e:
            logger.error(f"Gemini SDK error: {e}", exc_info=True)
            raise
    
    def _extract_json(self, text: str) -> Dict:
        """
        Extract JSON from Gemini response with multiple fallback strategies.
        """
        text = text.strip()
        
        # Strategy 1: Try parsing as-is (if response is pure JSON)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Look for markdown code block (```json ... ```)
        json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse markdown JSON: {e}")
        
        # Strategy 3: Find first { and last } (handles wrapped responses)
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            try:
                json_str = text[first_brace:last_brace + 1]
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse extracted JSON: {e}")
        
        # If all strategies fail, raise error with full context
        logger.error(f"Could not extract valid JSON from: {text[:500]}")
        raise ValueError("Could not extract valid JSON from Gemini response")
    
    def _process_gemini_response(self, gemini_result: Dict, original_items: List[Dict]) -> Dict:
        """
        Post-processes Gemini response to ensure consistency and calculate derived fields.
        """
        processed_items = []
        
        items_from_gemini = gemini_result.get("items", [])
        logger.info(f"Processing {len(items_from_gemini)} items from Gemini response")
        
        for item_result in items_from_gemini:
            # Find original item to get accurate cost
            original = next(
                (i for i in original_items if i['itemId'] == item_result['itemId']), 
                None
            )
            
            if not original:
                logger.warning(f"Item {item_result.get('itemId')} not found in original items")
                continue
            
            current_cost = original['currentCost']
            
            # Process suggestions and calculate savings
            suggestions = []
            for sugg in item_result.get('suggestions', [])[:3]:  # Top 3 only
                cost_savings = current_cost - sugg['estimatedCost']
                savings_percent = (cost_savings / current_cost * 100) if current_cost > 0 else 0
                
                suggestions.append({
                    "suggestedItemId": None,
                    "name": sugg['name'],
                    "estimatedCost": sugg['estimatedCost'],
                    "costSavings": round(cost_savings, 2),
                    "savingsPercent": round(savings_percent, 1),
                    "confidence": sugg.get('confidence', 0.7),
                    "rationale": sugg['rationale']
                })
            
            # Process removal suggestion
            never_used = item_result.get('neverUsedFlag', False)
            removal = item_result.get('removalSuggestion', {})
            
            processed_items.append({
                "itemId": item_result['itemId'],
                "name": item_result['name'],
                "currentCost": current_cost,
                "lastUsed": original.get('lastUsed'),
                "neverUsedFlag": never_used,
                "suggestions": suggestions,
                "removalSuggestion": {
                    "recommended": removal.get('recommended', never_used),
                    "reason": removal.get('reason'),
                    "actionableCheckboxId": f"chk_{item_result['itemId']}" if removal.get('recommended') else None
                }
            })
        
        logger.info(f"Processed {len(processed_items)} items successfully")
        return {"items": processed_items}

gemini_service = GeminiService()

# import google.generativeai as genai
# from app.config import get_settings
# from app.prompts import build_suggestion_prompt
# import json
# import re
# from typing import List, Dict
# import logging

# logger = logging.getLogger(__name__)
# settings = get_settings()

# # Configure Gemini
# genai.configure(api_key=settings.GOOGLE_API_KEY)

# class GeminiService:
#     def __init__(self):
#         self.model = genai.GenerativeModel(
#             model_name=settings.GEMINI_MODEL,
#             generation_config={
#                 "temperature": settings.GEMINI_TEMPERATURE,
#                 "max_output_tokens": settings.GEMINI_MAX_TOKENS,
#             }
#         )
    
#     async def generate_suggestions(
#         self, 
#         items: List[Dict], 
#         sub_grid: str, 
#         procedure_type: str = None
#     ) -> Dict:
#         """
#         Calls Gemini API to generate suggestions for items.
#         """
#         try:
#             prompt = build_suggestion_prompt(items, sub_grid, procedure_type)
            
#             logger.info(f"Calling Gemini for {len(items)} items in {sub_grid}")
            
#             response = self.model.generate_content(prompt)
            
#             # Extract JSON from response
#             raw_text = response.text
            
#             # Try to extract JSON if wrapped in markdown
#             json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', raw_text, re.DOTALL)
#             if json_match:
#                 json_text = json_match.group(1)
#             else:
#                 json_text = raw_text.strip()
            
#             # Parse JSON
#             result = json.loads(json_text)
            
#             # Validate and enrich response
#             return self._process_gemini_response(result, items)
            
#         except json.JSONDecodeError as e:
#             logger.error(f"Failed to parse Gemini response: {e}")
#             logger.error(f"Raw response: {response.text}")
#             raise ValueError("Gemini returned invalid JSON")
        
#         except Exception as e:
#             logger.error(f"Gemini API error: {e}")
#             raise
    
#     def _process_gemini_response(self, gemini_result: Dict, original_items: List[Dict]) -> Dict:
#         """
#         Post-processes Gemini response to ensure consistency and calculate derived fields.
#         """
#         processed_items = []
        
#         for item_result in gemini_result.get("items", []):
#             # Find original item to get accurate cost
#             original = next(
#                 (i for i in original_items if i['itemId'] == item_result['itemId']), 
#                 None
#             )
            
#             if not original:
#                 continue
            
#             current_cost = original['currentCost']
            
#             # Process suggestions and calculate savings
#             suggestions = []
#             for sugg in item_result.get('suggestions', [])[:3]:  # Top 3 only
#                 cost_savings = current_cost - sugg['estimatedCost']
#                 savings_percent = (cost_savings / current_cost * 100) if current_cost > 0 else 0
                
#                 suggestions.append({
#                     "suggestedItemId": None,  # We don't have CRM IDs yet
#                     "name": sugg['name'],
#                     "estimatedCost": sugg['estimatedCost'],
#                     "costSavings": round(cost_savings, 2),
#                     "savingsPercent": round(savings_percent, 1),
#                     "confidence": sugg.get('confidence', 0.7),
#                     "rationale": sugg['rationale']
#                 })
            
#             # Process removal suggestion
#             never_used = item_result.get('neverUsedFlag', False)
#             removal = item_result.get('removalSuggestion', {})
            
#             processed_items.append({
#                 "itemId": item_result['itemId'],
#                 "name": item_result['name'],
#                 "currentCost": current_cost,
#                 "lastUsed": original.get('lastUsed'),
#                 "neverUsedFlag": never_used,
#                 "suggestions": suggestions,
#                 "removalSuggestion": {
#                     "recommended": removal.get('recommended', never_used),
#                     "reason": removal.get('reason'),
#                     "actionableCheckboxId": f"chk_{item_result['itemId']}" if removal.get('recommended') else None
#                 }
#             })
        
#         return {"items": processed_items}

# gemini_service = GeminiService()