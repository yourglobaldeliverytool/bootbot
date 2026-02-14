# Modular Trading Bot - Architecture Documentation

## Overview

The trading bot is designed with a modular, pluggable architecture that allows for easy extension and customization of strategies, indicators, and notification systems. The system uses a registry-based approach for dynamic loading of components at runtime.

## Core Principles

1. **Modularity**: Each component (strategies, indicators, notifiers) is independent and can be developed/tested in isolation
2. **Pluggability**: Components can be added/removed without modifying core engine code
3. **Testability**: All components have clear interfaces and can be unit tested independently
4. **Extensibility**: New strategies, indicators, or notifiers can be added by implementing base interfaces

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         app.py                              │
│                    (Main Application)                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                      TradingEngine                          │
│                   (Core Orchestration)                       │
│  - Manages strategies, indicators, notifiers                │
│  - Executes strategies and generates signals                │
│  - Routes signals to notifiers                              │
└──────┬───────────────────────────────────┬──────────────────┘
       │                                   │
       ▼                                   ▼
┌──────────────┐                   ┌──────────────┐
│   Registries │                   │  DataLoader  │
│              │                   └──────────────┘
│  - Strategy  │
│  - Indicator │
│  - Notifier  │
└──────┬───────┘
       │
       ├───────────────────┬───────────────────┬─────────────────┐
       ▼                   ▼                   ▼                 ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  Strategies  │   │  Indicators  │   │  Notifiers   │   │   Utilities  │
│              │   │              │   │              │   │              │
│ - Trend      │   │ - SMA        │   │ - Telegram   │   │ - Logger     │
│ - MeanRev    │   │ - EMA        │   │ - Email      │   │ - DataLoader│
│ - Breakout   │   │ - RSI        │   │ - Slack      │   │              │
│ - Scalping   │   │ - MACD       │   │ - Webhook    │   │              │
│ - Arbitrage  │   │ - ATR        │   │              │   │              │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

## Module Descriptions

### Core Module (`bot/core/`)

#### interfaces.py
Defines abstract base classes that all components must implement:
- **Indicator**: Base class for technical indicators
  - `calculate(data)`: Calculate indicator values
  - `reset()`: Reset indicator state
  
- **Strategy**: Base class for trading strategies
  - `generate_signal(data)`: Generate trading signals
  - `set_parameters(params)`: Update strategy parameters
  - `add_indicator(indicator)`: Attach indicator to strategy
  
- **Notifier**: Base class for notification systems
  - `send_notification(message, data)`: Send notification

#### engine.py
Main trading engine that orchestrates all components:
- Loads and manages strategies, indicators, and notifiers
- Executes strategies on provided data
- Routes signals to active notifiers
- Maintains engine state and status

#### registry.py
Registry system for dynamic component loading:
- **StrategyRegistry**: Manages strategy classes
- **IndicatorRegistry**: Manages indicator classes
- **NotifierRegistry**: Manages notifier classes
- Supports dynamic loading from modules
- Creates instances on demand

### Strategies Module (`bot/strategies/`)

Trading strategy implementations. Each strategy:
- Inherits from `bot.core.interfaces.Strategy`
- Can use any combination of indicators
- Generates BUY/SELL/HOLD signals with confidence levels
- Provides reasoning for each signal

Available strategies:
- **Trend Following**: Uses moving averages to follow trends
- **Mean Reversion**: Exploits statistical mean reversion
- **Breakout**: Identifies price breakouts from ranges
- **Scalping**: Short-term high-frequency trading
- **Arbitrage**: Exploits price discrepancies

### Indicators Module (`bot/indicators/`)

Technical indicator implementations. Each indicator:
- Inherits from `bot.core.interfaces.Indicator`
- Calculates values from OHLCV data
- Maintains its own state (if needed)
- Can be used by multiple strategies

Available indicators:
- **SMA**: Simple Moving Average
- **EMA**: Exponential Moving Average
- **RSI**: Relative Strength Index
- **MACD**: Moving Average Convergence Divergence
- **ATR**: Average True Range

### Notifiers Module (`bot/notifiers/`)

Notification system implementations. Each notifier:
- Inherits from `bot.core.interfaces.Notifier`
- Sends formatted trading signals
- Can be enabled/disabled dynamically
- Optional and pluggable

Available notifiers:
- **Telegram**: Sends signals via Telegram bot
- **Email**: Sends signals via email
- **Slack**: Sends signals to Slack channels (extensible)

### Utils Module (`bot/utils/`)

Utility functions and helpers:
- **logger**: Centralized logging configuration
- **data_loader**: Data generation and loading utilities

### Config Module (`bot/config/`)

Configuration files:
- **config.yaml**: Main configuration file
  - Strategy settings and parameters
  - Indicator configurations
  - Notification settings
  - Data source configuration

## Workflow

### Initialization Flow

1. Load configuration from `config.yaml`
2. Initialize TradingEngine with config
3. Load indicators from config and register them
4. Load strategies from config and register them
5. Load notifiers from config and register them
6. Attach indicators to strategies as needed
7. Bot is ready for execution

### Execution Flow

1. Load OHLCV data (synthetic, CSV, or API)
2. Validate data format and content
3. For each active strategy:
   - Apply all attached indicators to data
   - Generate trading signal based on indicators
   - Calculate confidence level
   - Provide reasoning for signal
4. Collect all signals from strategies
5. Format and send notifications via active notifiers
6. Log execution results

### Signal Structure

Each signal generated by a strategy contains:
```python
{
    'strategy_name': 'trend_following',
    'signal': 'BUY',  # or 'SELL' or 'HOLD'
    'confidence': 0.85,  # 0.0 to 1.0
    'reason': 'Price crossed above 20-period SMA',
    'metadata': {
        'sma_20': 105.50,
        'price': 107.25,
        # Strategy-specific data
    },
    'timestamp': pd.Timestamp('2024-01-01 10:00:00')
}
```

## Adding New Components

### Adding a New Strategy

1. Create new file in `bot/strategies/`
2. Inherit from `bot.core.interfaces.Strategy`
3. Implement required methods:
   - `generate_signal(data)`
   - `set_parameters(parameters)`
4. Set `STRATEGY_NAME` constant
5. Add to `config.yaml` to enable
6. No changes to core code needed!

### Adding a New Indicator

1. Create new file in `bot/indicators/`
2. Inherit from `bot.core.interfaces.Indicator`
3. Implement required methods:
   - `calculate(data)`
   - `reset()`
4. Set `INDICATOR_NAME` constant
5. Add to `config.yaml` to enable
6. No changes to core code needed!

### Adding a New Notifier

1. Create new file in `bot/notifiers/`
2. Inherit from `bot.core.interfaces.Notifier`
3. Implement required method:
   - `send_notification(message, data)`
4. Set `NOTIFIER_NAME` constant
5. Add to `config.yaml` to enable
6. No changes to core code needed!

## Data Flow

```
┌─────────────┐
│   Config    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Engine    │◄─────┐
└──────┬──────┘      │
       │             │
       ▼             │
┌─────────────┐      │
│    Data     │──────┤
│  (OHLCV)    │      │
└──────┬──────┘      │
       │             │
       ▼             │
┌─────────────┐      │
│ Strategies  │──────┘
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Signals   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Notifiers  │
└─────────────┘
```

## Design Patterns Used

1. **Registry Pattern**: Dynamic component loading and management
2. **Strategy Pattern**: Pluggable trading algorithms
3. **Observer Pattern**: Notification system for signals
4. **Factory Pattern**: Creating component instances from registry
5. **Template Method**: Base classes define algorithm structure

## Testing Strategy

### Unit Tests
- Test each indicator independently with mock data
- Test each strategy independently with mock data
- Test each notifier independently with mock signals

### Integration Tests
- Test engine with multiple strategies
- Test indicator-strategy integration
- Test signal generation and notification flow

### Synthetic Data Tests
- Generate realistic OHLCV data
- Run all strategies on synthetic data
- Validate signal outputs
- Check for errors or edge cases

## Configuration Management

The system uses YAML configuration for easy customization:

- Enable/disable components
- Set component parameters
- Configure data sources
- Setup notification channels
- Control logging levels

## Extensibility Points

1. **New Strategies**: Add to `bot/strategies/`
2. **New Indicators**: Add to `bot/indicators/`
3. **New Notifiers**: Add to `bot/notifiers/`
4. **New Data Sources**: Extend `DataLoader`
5. **New Signal Formats**: Extend signal structure
6. **New Order Types**: Extend signal types

## Performance Considerations

- Indicators are calculated once per data update
- Strategies execute independently
- Notifications are sent asynchronously (in production)
- State management is component-specific
- Memory efficient with minimal data copying

## Security Considerations

- API tokens stored in config (not in code)
- Notification credentials encrypted (in production)
- Input validation on all data
- Error handling prevents crashes
- Logging for audit trail

## Future Enhancements

1. Real-time data feed integration
2. Database persistence for signals
3. Backtesting framework
4. Performance analytics dashboard
5. Web UI for monitoring
6. Multi-asset support
7. Risk management module
8. Position sizing algorithms
9. Order execution integration
10. Machine learning strategies