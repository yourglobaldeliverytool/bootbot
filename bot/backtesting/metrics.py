"""
Performance metrics calculation for backtesting.
"""

from typing import Dict, List, Any
import pandas as pd
import numpy as np


class PerformanceMetrics:
    """Calculate and store performance metrics."""
    
    @staticmethod
    def calculate(
        initial_capital: float,
        final_capital: float,
        trades: List[Dict[str, Any]],
        equity_curve: List[float]
    ) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""
        metrics = {}
        
        # Return metrics
        metrics['total_return'] = (final_capital - initial_capital) / initial_capital
        metrics['total_pnl'] = final_capital - initial_capital
        
        # Trade statistics
        if trades:
            metrics['num_trades'] = len(trades)
            
            # Calculate trade P&L
            trade_pnls = PerformanceMetrics._calculate_trade_pnls(trades)
            
            if trade_pnls:
                metrics['win_rate'] = sum(1 for pnl in trade_pnls if pnl > 0) / len(trade_pnls)
                metrics['num_winning_trades'] = sum(1 for pnl in trade_pnls if pnl > 0)
                metrics['num_losing_trades'] = sum(1 for pnl in trade_pnls if pnl < 0)
                
                winning_pnls = [pnl for pnl in trade_pnls if pnl > 0]
                losing_pnls = [pnl for pnl in trade_pnls if pnl < 0]
                
                metrics['avg_trade_pnl'] = np.mean(trade_pnls)
                
                if winning_pnls:
                    metrics['avg_winning_trade'] = np.mean(winning_pnls)
                    metrics['largest_win'] = max(winning_pnls)
                else:
                    metrics['avg_winning_trade'] = 0
                    metrics['largest_win'] = 0
                
                if losing_pnls:
                    metrics['avg_losing_trade'] = np.mean(losing_pnls)
                    metrics['largest_loss'] = min(losing_pnls)
                else:
                    metrics['avg_losing_trade'] = 0
                    metrics['largest_loss'] = 0
                
                # Profit factor
                gross_profit = sum(winning_pnls)
                gross_loss = abs(sum(losing_pnls))
                metrics['profit_factor'] = gross_profit / gross_loss if gross_loss > 0 else float('inf')
            else:
                metrics['win_rate'] = 0
                metrics['num_winning_trades'] = 0
                metrics['num_losing_trades'] = 0
                metrics['avg_trade_pnl'] = 0
                metrics['avg_winning_trade'] = 0
                metrics['avg_losing_trade'] = 0
                metrics['largest_win'] = 0
                metrics['largest_loss'] = 0
                metrics['profit_factor'] = 0
        else:
            metrics['num_trades'] = 0
            metrics['win_rate'] = 0
            metrics['num_winning_trades'] = 0
            metrics['num_losing_trades'] = 0
            metrics['avg_trade_pnl'] = 0
            metrics['avg_winning_trade'] = 0
            metrics['avg_losing_trade'] = 0
            metrics['largest_win'] = 0
            metrics['largest_loss'] = 0
            metrics['profit_factor'] = 0
        
        # Drawdown analysis
        if equity_curve:
            metrics['max_drawdown'] = PerformanceMetrics._calculate_max_drawdown(equity_curve)
            
            # Risk-adjusted returns
            returns = pd.Series(equity_curve).pct_change().dropna()
            if len(returns) > 0:
                metrics['sharpe_ratio'] = PerformanceMetrics._calculate_sharpe_ratio(returns)
                metrics['sortino_ratio'] = PerformanceMetrics._calculate_sortino_ratio(returns)
            else:
                metrics['sharpe_ratio'] = 0
                metrics['sortino_ratio'] = 0
        else:
            metrics['max_drawdown'] = 0
            metrics['sharpe_ratio'] = 0
            metrics['sortino_ratio'] = 0
        
        return metrics
    
    @staticmethod
    def _calculate_trade_pnls(trades: List[Dict[str, Any]]) -> List[float]:
        """Calculate P&L for each completed trade."""
        if not trades:
            return []
        
        pnls = []
        position = {}
        
        for trade in trades:
            trade_type = trade.get('type')
            quantity = trade.get('quantity', 0)
            price = trade.get('price', 0)
            symbol = trade.get('symbol', 'UNKNOWN')
            
            if symbol not in position:
                position[symbol] = {'quantity': 0, 'entry_price': 0}
            
            if trade_type == 'BUY':
                if position[symbol]['quantity'] == 0:
                    position[symbol]['quantity'] = quantity
                    position[symbol]['entry_price'] = price
            elif trade_type == 'SELL':
                if position[symbol]['quantity'] > 0:
                    pnl = (price - position[symbol]['entry_price']) * quantity
                    pnls.append(pnl)
                    position[symbol]['quantity'] = 0
        
        return pnls
    
    @staticmethod
    def _calculate_max_drawdown(equity_curve: List[float]) -> float:
        """Calculate maximum drawdown."""
        if len(equity_curve) < 2:
            return 0.0
        
        equity_series = pd.Series(equity_curve)
        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max
        return drawdown.min()
    
    @staticmethod
    def _calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sharpe ratio."""
        if len(returns) < 2:
            return 0.0
        
        daily_rf = risk_free_rate / 252
        excess_returns = returns - daily_rf
        
        if excess_returns.std() == 0:
            return 0.0
        
        sharpe = excess_returns.mean() / excess_returns.std() * np.sqrt(252)
        return sharpe
    
    @staticmethod
    def _calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
        """Calculate Sortino ratio."""
        if len(returns) < 2:
            return 0.0
        
        daily_rf = risk_free_rate / 252
        excess_returns = returns - daily_rf
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0
        
        sortino = excess_returns.mean() / downside_returns.std() * np.sqrt(252)
        return sortino