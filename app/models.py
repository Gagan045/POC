from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

# Request Models
class ItemInput(BaseModel):
    itemId: str
    name: str
    currentCost: float
    lastUsed: Optional[str] = None  # ISO date or "never"
    catalogNo: Optional[str] = None
    category: Optional[str] = None  # "supply", "instrument", "medication"
    unitOfMeasure: Optional[str] = None

class SuggestionRequest(BaseModel):
    spcId: str
    subGrid: Literal["Supplies", "Instruments", "Medicine", "CardSummary"]
    items: List[ItemInput]
    procedureType: Optional[str] = None  # e.g., "COLONOSCOPY"
    facilityId: Optional[str] = None

# Response Models
class AlternativeSuggestion(BaseModel):
    suggestedItemId: Optional[str] = None  # Will be null from Gemini
    name: str
    estimatedCost: float
    costSavings: float = Field(description="Dollar amount saved vs current")
    savingsPercent: float = Field(description="Percentage saved vs current")
    confidence: float = Field(ge=0, le=1)
    rationale: str

class RemovalSuggestion(BaseModel):
    recommended: bool
    reason: Optional[str] = None
    actionableCheckboxId: Optional[str] = None

class ItemAnalysis(BaseModel):
    itemId: str
    name: str
    currentCost: float
    lastUsed: Optional[str]
    neverUsedFlag: bool
    suggestions: List[AlternativeSuggestion] = []
    removalSuggestion: RemovalSuggestion

class UIHints(BaseModel):
    displayMode: Literal["embed", "panel", "modal", "sidepanel"] = "panel"
    priorityItems: List[str] = []  # Item IDs to highlight
    pagination: dict = {"page": 1, "pageSize": 20}

class MetaInfo(BaseModel):
    generatedAt: datetime
    model: str
    executionMs: int

class SuggestionResponse(BaseModel):
    spcId: str
    subGrid: str
    itemsAnalyzed: List[ItemAnalysis]
    summary: str  # Human-readable summary
    uiHints: UIHints
    meta: MetaInfo

# Removal Request Models
class RemovalItem(BaseModel):
    itemId: str
    checkboxId: str

class RemovalRequest(BaseModel):
    spcId: str
    subGrid: str
    itemsToRemove: List[RemovalItem]
    userId: str
    reason: Optional[str] = None