"""Strategy Manager for parallel execution and confluence calculation."""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import pandas as pd

from bot.core.registry import StrategyRegistry
from bot.core.interfaces import Strategy

logger = logging.getLogger(__name__)


class StrategyManager:
    """Manager for running strategies in parallel and calculating confluence."""
    
    def __init__(self, strategy_config: Dict[str, Any]):
        """
        Initialize Strategy Manager.
        
        Args:
            strategy_config: Strategy configuration from config.yaml
        """
        self.strategy_config = strategy_config
        self.registry = StrategyRegistry()
        self.strategies: Dict[str, Strategy] = {}
        self.active_strategies: List[str] = []
        
        # Load strategies from config
        self._load_strategies()
    
    def _load_strategies(self):
        """Load enabled strategies from configuration."""
        for strategy_name, config in self.strategy_config.items():
            if config.get('enabled', False):
                try:
                    strategy = self.registry.get(strategy_name)
                    if strategy:
                        self.strategies[strategy_name] = strategy(**config.get('parameters', {}))
                        self.active_strategies.append(strategy_name)
                        logger.info(f"✅ Loaded strategy: {strategy_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load strategy {strategy_name}: {e}")
        
        logger.info(f"📊 Active strategies: {len(self.active_strategies)}")
    
    def run_all_strategies(self, data: pd.DataFrame, indicators: Dict[str, pd.Series]) -> List[Dict[str, Any]]:
        """
        Run all active strategies in parallel.
        
        Args:
            data: OHLCV data
            indicators: Calculated indicator values
            
        Returns:
            List of signals from all strategies
        """
        if not self.active_strategies:
            return []
        
        signals = []
        
        # Run strategies in parallel using thread pool
        with ThreadPoolExecutor(max_workers=len(self.active_strategies)) as executor:
            futures = {
                executor.submit(
                    self._run_single_strategy, 
                    strategy_name, 
                    data, 
                    indicators
                ): strategy_name for strategy_name in self.active_strategies
            }
            
            for future in as_completed(futures):
                strategy_name = futures[future]
                try:
                    signal = future.result()
                    if signal:
                        signals.append(signal)
                except Exception as e:
                    logger.error(f"❌ Error running strategy {strategy_name}: {e}")
        
        return signals
    
    def _run_single_strategy(self, strategy_name: str, data: pd.DataFrame, 
                            indicators: Dict[str, pd.Series]) -> Optional[Dict[str, Any]]:
        """
        Run a single strategy.
        
        Args:
            strategy_name: Name of the strategy to run
            data: OHLCV data
            indicators: Calculated indicator values
            
        Returns:
            Signal dictionary or None
        """
        try:
            strategy = self.strategies.get(strategy_name)
            if not strategy:
                return None
            
            signal = strategy.generate_signal(data, indicators)
            
            return {
                'strategy': strategy_name,
                'signal_type': signal.get('signal_type', 'HOLD'),
                'score': signal.get('score', 0),
                'reason': signal.get('reason', ''),
                'timestamp': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"❌ Error in strategy {strategy_name}: {e}")
            return None
    
    def calculate_confluence(self, signals: List[Dict[str, Any]], 
                           indicators: Dict[str, pd.Series],
                           data: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate overall confluence and confidence.
        
        Args:
            signals: List of strategy signals
            indicators: Calculated indicator values
            data: OHLCV data
            
        Returns:
            Confluence result with confidence score
        """
        if not signals:
            return {
                'base_confidence': 0.0,
                'final_confidence': 0.0,
                'agreed_strategies': 0,
                'total_strategies': len(self.active_strategies),
                'signal_type': 'HOLD',
                'modifiers': {}
            }
        
        # Count signals by type
        buy_count = sum(1 for s in signals if s['signal_type'] == 'BUY')
        sell_count = sum(1 for s in signals if s['signal_type'] == 'SELL')
        hold_count = sum(1 for s in signals if s['signal_type'] == 'HOLD')
        
        # Determine dominant signal
        if buy_count > sell_count:
            signal_type = 'BUY'
            agreed_count = buy_count
        elif sell_count > buy_count:
            signal_type = 'SELL'
            agreed_count = sell_count
        else:
            signal_type = 'HOLD'
            agreed_count = 0
        
        # Base confidence from strategy alignment
        total_strategies = len(self.active_strategies)
        base_confidence = (agreed_count / total_strategies) * 100 if total_strategies > 0 else 0
        
        # Modifiers
        modifiers = {}
        modifier_value = 0.0
        
        # Volume confirmation modifier
        if 'volume' in data.columns:
            avg_volume = data['volume'].tail(20).mean()
            current_volume = data['volume'].iloc[-1]
            if current_volume > avg_volume * 1.2:
                modifiers['volume_confirmation'] = 5.0
                modifier_value += 5.0
        
        # ADX strength modifier
        if 'adx' in indicators:
            adx_value = indicators['adx'].iloc[-1]
            if adx_value > 25:
                modifiers['adx_strength'] = 5.0
                modifier_value += 5.0
            elif adx_value > 40:
                modifiers['adx_strength'] = 10.0
                modifier_value += 10.0
        
        # RSI overbought/oversold check for contrarian signals
        if 'rsi' in indicators:
            rsi_value = indicators['rsi'].iloc[-1]
            if signal_type == 'BUY' and rsi_value < 30:
                modifiers['rsi_oversold'] = 10.0
                modifier_value += 10.0
            elif signal_type == 'SELL' and rsi_value > 70:
                modifiers['rsi_overbought'] = 10.0
                modifier_value += 10.0
        
        # Final confidence (clamped between 0-100)
        final_confidence = max(0.0, min(100.0, base_confidence + modifier_value))
        
        return {
            'base_confidence': round(base_confidence, 2),
            'final_confidence': round(final_confidence, 2),
            'agreed_strategies': agreed_count,
            'total_strategies': total_strategies,
            'signal_type': signal_type,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'hold_count': hold_count,
            'modifiers': modifiers,
            'strategies': [s['strategy'] for s in signals if s['signal_type'] == signal_type]
        }
    
    def get_signal_summary(self, confluence: Dict[str, Any]) -> str:
        """
        Get a human-readable summary of the confluence result.
        
        Args:
            confluence: Confluence result from calculate_confluence
            
        Returns:
            Summary string
        """
        confidence = confluence['final_confidence']
        signal_type = confluence['signal_type']
        
        confidence_label = self._get_confidence_label(confidence)
        
        summary = (
            f"{signal_type} signal with {confidence:.1f}% confidence "
            f"({confidence_label}). "
            f"{confluence['agreed_strategies']}/{confluence['total_strategies']} "
            f"strategies agree."
        )
        
        if confluence['modifiers']:
            modifier_list = [f"{k}: +{v}%" for k, v in confluence['modifiers'].items()]
            summary += f" Modifiers: {', '.join(modifier_list)}"
        
        return summary
    
    def _get_confidence_label(self, confidence: float) -> str:
        """Get confidence label based on confidence value."""
        if confidence >= 80:
            return 'VERY HIGH'
        elif confidence >= 60:
            return 'HIGH'
        elif confidence >= 30:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_active_strategies(self) -> List[str]:
        """Get list of active strategy names."""
        return self.active_strategies.copy()