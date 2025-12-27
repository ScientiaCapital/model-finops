"""
Arbitrage REST API Router.

Provides endpoints for model arbitrage detection and cost optimization.
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user_id
from app.models.arbitrage import (
    ArbitrageAnalysisRequest,
    ArbitrageAnalysisResponse,
    ArbitrageOpportunity,
    ModelProfile,
    ModelCapability,
)
from app.services.arbitrage_service import ArbitrageService
from app.arbitrage.capability_registry import CapabilityRegistry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/arbitrage",
    tags=["Arbitrage"],
    responses={404: {"description": "Not found"}},
)


def get_arbitrage_service() -> ArbitrageService:
    """Dependency to get arbitrage service instance."""
    # TODO: Inject Supabase client when available
    return ArbitrageService()


@router.post("/analyze", response_model=ArbitrageAnalysisResponse)
async def analyze_prompt(
    request: ArbitrageAnalysisRequest,
    user_id: str = Depends(get_current_user_id),
    service: ArbitrageService = Depends(get_arbitrage_service),
) -> ArbitrageAnalysisResponse:
    """
    Analyze a prompt to find cost optimization opportunities.

    Detects required capabilities from the prompt and finds cheaper
    model alternatives that can handle the task.

    Returns:
        ArbitrageAnalysisResponse with opportunities and recommendations
    """
    try:
        response = service.analyze_prompt(
            prompt=request.prompt,
            current_model=request.current_model,
            user_id=user_id,
            input_tokens=request.input_tokens or 0,
            output_tokens=request.output_tokens or 0,
        )
        return response
    except Exception as e:
        logger.error(f"Error analyzing prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze prompt")


@router.get("/opportunities", response_model=List[dict])
async def list_opportunities(
    limit: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    service: ArbitrageService = Depends(get_arbitrage_service),
) -> List[dict]:
    """
    List recent arbitrage opportunities for the user.

    Returns:
        List of recent opportunities with savings information
    """
    try:
        opportunities = await service.get_user_opportunities(user_id, limit)
        return opportunities
    except Exception as e:
        logger.error(f"Error listing opportunities: {e}")
        raise HTTPException(status_code=500, detail="Failed to list opportunities")


@router.get("/savings-report")
async def get_savings_report(
    days: int = Query(30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id),
    service: ArbitrageService = Depends(get_arbitrage_service),
) -> dict:
    """
    Get savings report showing potential vs actual savings.

    Returns:
        Report with total potential savings, actual savings, and rates
    """
    try:
        report = await service.get_savings_report(user_id, days)
        return report
    except Exception as e:
        logger.error(f"Error generating savings report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.get("/models/{model_id}/alternatives", response_model=List[ModelProfile])
async def get_model_alternatives(
    model_id: str,
    capabilities: Optional[str] = Query(
        None,
        description="Comma-separated capability names (e.g., 'code_gen,reasoning')",
    ),
    service: ArbitrageService = Depends(get_arbitrage_service),
) -> List[ModelProfile]:
    """
    Get cheaper alternatives for a specific model.

    Args:
        model_id: The model ID to find alternatives for
        capabilities: Optional filter by required capabilities

    Returns:
        List of cheaper model profiles sorted by price
    """
    try:
        # Parse capabilities
        cap_list = None
        if capabilities:
            try:
                cap_list = [
                    ModelCapability(c.strip())
                    for c in capabilities.split(",")
                    if c.strip()
                ]
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid capability: {e}",
                )

        alternatives = service.get_alternatives_for_model(model_id, cap_list)
        return alternatives
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alternatives: {e}")
        raise HTTPException(status_code=500, detail="Failed to get alternatives")


@router.get("/models", response_model=List[ModelProfile])
async def list_all_models() -> List[ModelProfile]:
    """
    List all models in the capability registry.

    Returns:
        List of all model profiles with capabilities and pricing
    """
    registry = CapabilityRegistry()
    return registry.get_all_models()


@router.get("/models/by-provider/{provider}", response_model=List[ModelProfile])
async def list_models_by_provider(provider: str) -> List[ModelProfile]:
    """
    List models from a specific provider.

    Args:
        provider: Provider name (e.g., 'gemini', 'anthropic', 'groq')

    Returns:
        List of model profiles from the provider
    """
    registry = CapabilityRegistry()
    models = registry.get_models_by_provider(provider)
    if not models:
        raise HTTPException(
            status_code=404,
            detail=f"No models found for provider: {provider}",
        )
    return models


@router.get("/models/by-capability/{capability}", response_model=List[ModelProfile])
async def list_models_by_capability(
    capability: str,
    min_level: Optional[str] = Query(None, description="Minimum capability level"),
) -> List[ModelProfile]:
    """
    List models with a specific capability.

    Args:
        capability: Capability name (e.g., 'code_gen', 'reasoning')
        min_level: Optional minimum level (basic, intermediate, advanced, expert)

    Returns:
        List of model profiles with the capability
    """
    try:
        cap = ModelCapability(capability)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid capability: {capability}",
        )

    from app.models.arbitrage import CapabilityLevel
    level = None
    if min_level:
        try:
            level = CapabilityLevel(min_level)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid capability level: {min_level}",
            )

    registry = CapabilityRegistry()
    models = registry.get_models_with_capability(cap, level)
    return models


@router.get("/cheapest/{capability}", response_model=ModelProfile)
async def get_cheapest_model(
    capability: str,
    min_level: Optional[str] = Query(None, description="Minimum capability level"),
) -> ModelProfile:
    """
    Get the cheapest model for a capability.

    Args:
        capability: Required capability name
        min_level: Optional minimum level

    Returns:
        The cheapest model profile with the capability
    """
    try:
        cap = ModelCapability(capability)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid capability: {capability}",
        )

    from app.models.arbitrage import CapabilityLevel
    level = None
    if min_level:
        try:
            level = CapabilityLevel(min_level)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid capability level: {min_level}",
            )

    registry = CapabilityRegistry()
    model = registry.get_cheapest_model(cap, level)
    if not model:
        raise HTTPException(
            status_code=404,
            detail=f"No model found with capability: {capability}",
        )
    return model
