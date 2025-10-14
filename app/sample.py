from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from datetime import datetime
import logging
import traceback

from app.config import get_settings
from app.models import (
    SuggestionRequest, 
    SuggestionResponse, 
    ItemAnalysis,
    UIHints,
    MetaInfo,
    RemovalRequest
)
from app.gemini_service import gemini_service
from app.prompts import build_summary_prompt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Health Check
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/", tags=["System"])
async def root():
    return {
        "message": "SPC Suggestion API is running",
        "version": settings.API_VERSION,
        "docs": "/api/docs"
    }


# Main Suggestion Endpoint
@app.post(
    "/api/spc/suggestions",
    response_model=SuggestionResponse,
    tags=["Suggestions"],
    summary="Generate SPC Suggestions",
    description="Generates cost-saving suggestions and removal recommendations for SPC items."
)
async def generate_suggestions(request: SuggestionRequest):
    start_time = time.time()
    
    try:
        logger.info("=" * 60)
        logger.info("📥 New request received")
        logger.info(f"SPC ID: {request.spcId}")
        logger.info(f"Sub-grid: {request.subGrid}")
        logger.info(f"Items count: {len(request.items)}")
        logger.info(f"Procedure type: {request.procedureType}")
        
        # Validate input
        if not request.items:
            raise HTTPException(status_code=400, detail="No items provided for analysis")
        
        if len(request.items) > 50:
            raise HTTPException(status_code=400, detail="Maximum 50 items per request")
        
        # Convert items to dict for Gemini
        items_dict = [item.model_dump() for item in request.items]
        logger.info("✓ Items converted to dict format")
        
        # Call Gemini Service
        logger.info("🤖 Calling Gemini API...")
        gemini_result = await gemini_service.generate_suggestions(
            items=items_dict,
            sub_grid=request.subGrid,
            procedure_type=request.procedureType
        )
        logger.info("✓ Gemini API call successful")
        
        # Map to response model
        items_analyzed = [
            ItemAnalysis(**item_data) 
            for item_data in gemini_result['items']
        ]
        logger.info(f"✓ Analyzed {len(items_analyzed)} items")
        
        # Generate human-readable summary
        summary_data = [item.model_dump() for item in items_analyzed]
        summary = build_summary_prompt(summary_data)
        
        # Identify priority items
        priority_items = []
        for item in items_analyzed:
            if item.suggestions:
                max_savings = max([s.costSavings for s in item.suggestions])
                if max_savings > 50:
                    priority_items.append(item.itemId)
            if item.removalSuggestion.recommended:
                priority_items.append(item.itemId)
        
        # Build response
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        response = SuggestionResponse(
            spcId=request.spcId,
            subGrid=request.subGrid,
            itemsAnalyzed=items_analyzed,
            summary=summary,
            uiHints=UIHints(
                displayMode="panel",
                priorityItems=priority_items[:5],
                pagination={"page": 1, "pageSize": len(items_analyzed)}
            ),
            meta=MetaInfo(
                generatedAt=datetime.utcnow(),
                model=settings.GEMINI_MODEL,
                executionMs=execution_time_ms
            )
        )
        
        logger.info(f"✅ Request completed in {execution_time_ms}ms")
        logger.info("=" * 60)
        return response
        
    except ValueError as e:
        logger.error(f"❌ Validation error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=422, detail=str(e))
    
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500, 
            detail=f"Internal server error: {str(e)}"
        )


# Removal Endpoint (Phase 2 - Placeholder)
@app.post("/api/spc/remove-items", tags=["Suggestions"])
async def remove_items(request: RemovalRequest):
    logger.info(f"Removal request received for {len(request.itemsToRemove)} items (not implemented yet)")
    
    return {
        "status": "not_implemented",
        "message": "Removal functionality will be enabled in Phase 2",
        "itemsRequested": len(request.itemsToRemove)
    }


# Error Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting SPC Suggestion API...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
