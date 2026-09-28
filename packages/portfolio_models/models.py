"""Normalized portfolio models with validation."""

import math
from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SecurityType(StrEnum):
    """Security type enumeration."""
    STOCK = "STOCK"
    OPTION = "OPTION"


class OptionType(StrEnum):
    """Option type enumeration."""
    CALL = "CALL"
    PUT = "PUT"


class StrategyType(StrEnum):
    """Strategy type enumeration."""
    COLLAR = "COLLAR"
    COVERED_CALL = "COVERED_CALL"
    PROTECTIVE_PUT = "PROTECTIVE_PUT"
    CALENDAR_CALL = "CALENDAR_CALL"
    CALENDAR_PUT = "CALENDAR_PUT"
    DIAGONAL = "DIAGONAL"
    VERTICAL_CALL = "VERTICAL_CALL"
    VERTICAL_PUT = "VERTICAL_PUT"
    LONG_CALL = "LONG_CALL"
    LONG_PUT = "LONG_PUT"
    SHORT_CALL = "SHORT_CALL"
    SHORT_PUT = "SHORT_PUT"
    STOCK = "STOCK"
    UNMATCHED = "UNMATCHED"


class Position(BaseModel):
    """Normalized position with validation.

    Represents a single position in a portfolio with stable id, account details,
    security information, and optional market valuations.
    """
    model_config = {"frozen": True}

    id: str = Field(..., description="Stable position identifier")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Security symbol")
    currency: str = Field(..., description="Currency code")
    security_type: SecurityType = Field(..., description="Security type")
    quantity: float = Field(..., description="Signed quantity (positive=long, negative=short)")

    # Option-specific fields (required for OPTION, must be None for STOCK)
    option_type: OptionType | None = Field(None, description="Option type (CALL/PUT)")
    strike: float | None = Field(None, description="Strike price")
    expiration: date | None = Field(None, description="Expiration date")

    # Multiplier and pricing
    multiplier: float = Field(..., description="Contract multiplier (positive, 1 for stocks)")
    market_price: float | None = Field(None, description="Current market price per share/contract")
    market_value: float | None = Field(None, description="Total market value")
    unrealized_pnl: float | None = Field(None, description="Unrealized profit/loss")
    underlying_price: float | None = Field(None, description="Underlying security price")

    @field_validator("quantity", "multiplier", "market_price", "market_value", "unrealized_pnl", "underlying_price", "strike")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        """Reject non-finite numeric values."""
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v

    @field_validator("multiplier")
    @classmethod
    def validate_positive_multiplier(cls, v: float) -> float:
        """Ensure multiplier is positive."""
        if v <= 0:
            raise ValueError(f"Multiplier must be positive, got {v}")
        return v

    @model_validator(mode="after")
    def validate_option_fields(self) -> "Position":
        """Validate option-specific constraints."""
        if self.security_type == SecurityType.OPTION:
            # Option contracts require complete terms to participate in matching
            # Incomplete terms are preserved but won't match
            if self.option_type is not None or self.strike is not None or self.expiration is not None:
                # If any option field is set, validate what we have
                if self.strike is not None and self.strike <= 0:
                    raise ValueError(f"Strike must be positive, got {self.strike}")

            # Whole option quantities (integral)
            if not float(self.quantity).is_integer():
                raise ValueError(f"Option quantity must be whole number, got {self.quantity}")

        if self.security_type == SecurityType.STOCK:
            # Stock must not have option fields
            if self.option_type is not None or self.strike is not None or self.expiration is not None:
                raise ValueError("Stock positions cannot have option-specific fields")
            # Stock multiplier must be 1
            if self.multiplier != 1.0:
                raise ValueError(f"Stock multiplier must be 1, got {self.multiplier}")

        return self


class StrategyLeg(BaseModel):
    """Allocated leg within a strategy.

    References source position by id and tracks allocated quantity with prorated values.
    """
    model_config = {"frozen": True}

    position_id: str = Field(..., description="Source position identifier")
    allocated_quantity: float = Field(..., description="Signed allocated quantity")
    allocated_value: float | None = Field(None, description="Prorated market value")
    allocated_pnl: float | None = Field(None, description="Prorated unrealized P&L")

    @field_validator("allocated_quantity", "allocated_value", "allocated_pnl")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        """Reject non-finite numeric values."""
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v


class StrategyPerformance(BaseModel):
    """Strategy lifecycle performance summary.

    Tracks realized P&L, fees, and total performance since opening.
    Frontend contract: source, opened_at, realized_pnl, fees, total_pnl, reason.
    """
    model_config = {"frozen": True}

    source: Literal['mock_history', 'unavailable'] = Field(..., description="Data source")
    opened_at: datetime | None = Field(None, description="Strategy opening timestamp (timezone-aware)")
    realized_pnl: float | None = Field(None, description="Realized profit/loss (excludes fees if pnl_excludes_fees)")
    fees: float | None = Field(None, description="Total lifecycle fees")
    total_pnl: float | None = Field(None, description="Total P&L (realized + unrealized - fees)")
    reason: str | None = Field(None, description="Human-readable unavailability reason if applicable")

    @field_validator("realized_pnl", "fees", "total_pnl")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        """Reject non-finite numeric values."""
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v

    @field_validator("fees")
    @classmethod
    def validate_non_negative_fees(cls, v: float | None) -> float | None:
        """Ensure fees are non-negative."""
        if v is not None and v < 0:
            raise ValueError(f"Fees must be non-negative, got {v}")
        return v


class Strategy(BaseModel):
    """Recognized strategy with allocated legs.

    Represents a matched trading strategy with deterministic id, type classification,
    allocated position legs, and aggregated valuations.
    """
    model_config = {"frozen": True}

    id: str = Field(..., description="Deterministic strategy identifier")
    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Underlying symbol")
    currency: str = Field(..., description="Currency code")
    strategy_type: StrategyType = Field(..., description="Strategy classification")
    quantity: float = Field(..., description="Strategy unit quantity (positive)")
    name: str = Field(..., description="Human-readable strategy name")
    legs: list[StrategyLeg] = Field(..., description="Allocated position legs")
    market_value: float | None = Field(None, description="Aggregate market value")
    unrealized_pnl: float | None = Field(None, description="Aggregate unrealized P&L")
    confidence: float = Field(..., description="Rule certainty level (0..1)")
    explanation: str = Field(..., description="Matching explanation")
    performance: StrategyPerformance | None = None

    @field_validator("quantity", "market_value", "unrealized_pnl", "confidence")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        """Reject non-finite numeric values."""
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v

    @field_validator("quantity")
    @classmethod
    def validate_positive_quantity(cls, v: float) -> float:
        """Ensure strategy quantity is positive."""
        if v <= 0:
            raise ValueError(f"Strategy quantity must be positive, got {v}")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence_range(cls, v: float) -> float:
        """Ensure confidence is in range 0..1."""
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"Confidence must be in range 0..1, got {v}")
        return v


class AccountMetrics(BaseModel):
    """Account-level financial metrics."""
    model_config = {"frozen": True}

    currency: str = Field(..., description="Account currency")
    net_liquidation: float | None = Field(None, description="Net liquidation value")
    cash: float | None = Field(None, description="Cash balance")
    daily_pnl: float | None = Field(None, description="Daily profit/loss")
    unrealized_pnl: float | None = Field(None, description="Unrealized profit/loss")
    maintenance_margin: float | None = Field(None, description="Maintenance margin requirement")
    excess_liquidity: float | None = Field(None, description="Excess liquidity")
    buying_power: float | None = Field(None, description="Available buying power")

    @field_validator("net_liquidation", "cash", "daily_pnl", "unrealized_pnl",
                     "maintenance_margin", "excess_liquidity", "buying_power")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        """Reject non-finite numeric values."""
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v


class Underlying(BaseModel):
    """Underlying summary grouping positions and strategies.

    Groups original positions and recognized strategies by symbol,
    with net value, P&L, and current price.
    """
    model_config = {"frozen": True}

    account_id: str = Field(..., description="Account identifier")
    symbol: str = Field(..., description="Underlying symbol")
    currency: str = Field(..., description="Currency code")
    positions: list[Position] = Field(..., description="Original positions for this underlying")
    strategies: list[Strategy] = Field(..., description="Recognized strategies for this underlying")
    net_value: float | None = Field(None, description="Total net market value")
    net_pnl: float | None = Field(None, description="Total unrealized P&L")
    underlying_price: float | None = Field(None, description="Current underlying price")

    @field_validator("net_value", "net_pnl", "underlying_price")
    @classmethod
    def validate_finite(cls, v: float | None) -> float | None:
        """Reject non-finite numeric values."""
        if v is not None and not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v


class StrategyHistoryLeg(BaseModel):
    """Allocated leg signature within history record."""
    model_config = {"frozen": True}

    position_id: str = Field(..., description="Source position identifier")
    allocated_quantity: float = Field(..., description="Signed allocated quantity")

    @field_validator("allocated_quantity")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        """Reject non-finite numeric values."""
        if not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v


class StrategyHistory(BaseModel):
    """Strategy lifecycle history record.

    Records exact allocated leg signature, opening timestamp, realized P&L, and fees.
    Matched to strategies by account_id, currency, and exact allocated leg signature.
    """
    model_config = {"frozen": True}

    strategy_id: str | None = Field(None, description="Optional strategy identifier")
    account_id: str = Field(..., description="Account identifier")
    currency: str = Field(..., description="Currency code")
    legs: list[StrategyHistoryLeg] = Field(..., description="Exact allocated leg signature")
    opened_at: datetime = Field(..., description="Strategy opening timestamp (timezone-aware)")
    realized_pnl: float = Field(..., description="Realized profit/loss")
    fees: float = Field(..., description="Total lifecycle fees (non-negative)")
    complete: bool = Field(False, description="Whether history is complete")
    pnl_excludes_fees: bool = Field(False, description="Whether both realized and unrealized P&L exclude fees")

    @field_validator("opened_at")
    @classmethod
    def validate_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure opened_at is timezone-aware."""
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError(f"opened_at must be timezone-aware, got naive datetime {v}")
        return v

    @field_validator("legs")
    @classmethod
    def validate_legs_nonempty_unique(cls, v: list[StrategyHistoryLeg]) -> list[StrategyHistoryLeg]:
        """Ensure legs are non-empty with unique position_ids."""
        if not v:
            raise ValueError("legs must not be empty")
        position_ids = [leg.position_id for leg in v]
        if len(position_ids) != len(set(position_ids)):
            duplicates = [pid for pid in position_ids if position_ids.count(pid) > 1]
            raise ValueError(f"Duplicate position_ids in legs: {set(duplicates)}")
        return v

    @field_validator("realized_pnl", "fees")
    @classmethod
    def validate_finite(cls, v: float) -> float:
        """Reject non-finite numeric values."""
        if not math.isfinite(v):
            raise ValueError(f"Value must be finite, got {v}")
        return v

    @field_validator("fees")
    @classmethod
    def validate_non_negative_fees(cls, v: float) -> float:
        """Ensure fees are non-negative."""
        if v < 0:
            raise ValueError(f"Fees must be non-negative, got {v}")
        return v



class Snapshot(BaseModel):
    """Portfolio snapshot at a point in time.

    Fixed snapshot with timestamp, account metrics, validated positions, and optional history.
    Rejects duplicate position ids.
    """
    model_config = {"frozen": True}

    as_of: datetime = Field(..., description="Snapshot timestamp")
    account: AccountMetrics = Field(..., description="Account-level metrics")
    positions: list[Position] = Field(..., description="All portfolio positions")
    strategy_history: list[StrategyHistory] = Field(default_factory=list, description="Strategy lifecycle history records")

    @model_validator(mode="after")
    def validate_no_duplicate_ids(self) -> "Snapshot":
        """Reject duplicate position ids."""
        ids = [p.id for p in self.positions]
        if len(ids) != len(set(ids)):
            duplicates = [pid for pid in ids if ids.count(pid) > 1]
            raise ValueError(f"Duplicate position ids found: {set(duplicates)}")
        return self
