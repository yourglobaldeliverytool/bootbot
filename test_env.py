#!/usr/bin/env python3
"""
APEX SIGNAL™ - Import Verification Test
Validates that all critical dependencies and modules can be imported without errors.
Exit code 0 = all imports OK, exit code 1 = import failures.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


# Critical dependencies that must be importable
CRITICAL_DEPS = [
    'pandas',
    'numpy',
    'yaml',
    'requests',
    'asyncio',
    'aiohttp',
    'fastapi',
    'uvicorn',
]

# Optional dependencies (logged but not blocking)
OPTIONAL_DEPS = [
    'alpaca_trade_api',
    'polygon_api_client',
    'python_telegram_bot',
    'ccxt',
]

# Critical bot modules that must import successfully
CRITICAL_MODULES = [
    'config',
    'bot.core.interfaces',
    'bot.core.registry',
    'bot.core.engine',
    'bot.core.price_manager',
    'bot.core.circuit_breaker',
    'bot.core.rate_limiter',
    'bot.utils.env_loader',
    'bot.utils.logger',
    'bot.connectors.base',
    'bot.connectors.multi_source',
    'bot.strategies.strategy_manager',
    'bot.api.app',
]

# Optional bot modules (logged but not blocking)
OPTIONAL_MODULES = [
    'bot.connectors.alpaca',
    'bot.connectors.polygon',
    'bot.connectors.yahoo_finance',
    'bot.connectors.coingecko',
    'bot.connectors.coincap',
    'bot.notifiers.telegram_notifier',
    'bot.notifiers.email_notifier',
]


def test_import(module_name: str, critical: bool = True) -> bool:
    """
    Test if a module can be imported.
    
    Args:
        module_name: Name of the module to import
        critical: If True, failure will exit with error code
        
    Returns:
        True if import succeeded, False otherwise
    """
    try:
        __import__(module_name)
        status = "✅ PASS"
        logger.info(f"{status}: {module_name}")
        return True
    except ImportError as e:
        status = "❌ FAIL" if critical else "⚠️  SKIP"
        logger.error(f"{status}: {module_name} - {str(e)}")
        return not critical  # Return False only if critical


def main():
    """Run all import tests."""
    logger.info("=" * 60)
    logger.info("🧪 APEX SIGNAL™ - Import Verification Test")
    logger.info("=" * 60)
    
    all_passed = True
    
    # Test critical dependencies
    logger.info("\n📦 Testing Critical Dependencies...")
    critical_deps_passed = 0
    for dep in CRITICAL_DEPS:
        if test_import(dep, critical=True):
            critical_deps_passed += 1
        else:
            all_passed = False
    
    logger.info(f"Critical Dependencies: {critical_deps_passed}/{len(CRITICAL_DEPS)} passed")
    
    # Test optional dependencies
    logger.info("\n📦 Testing Optional Dependencies (may be missing)...")
    optional_deps_passed = 0
    for dep in OPTIONAL_DEPS:
        if test_import(dep, critical=False):
            optional_deps_passed += 1
    
    logger.info(f"Optional Dependencies: {optional_deps_passed}/{len(OPTIONAL_DEPS)} available")
    
    # Test critical modules
    logger.info("\n🧩 Testing Critical Bot Modules...")
    critical_modules_passed = 0
    for module in CRITICAL_MODULES:
        if test_import(module, critical=True):
            critical_modules_passed += 1
        else:
            all_passed = False
    
    logger.info(f"Critical Modules: {critical_modules_passed}/{len(CRITICAL_MODULES)} passed")
    
    # Test optional modules
    logger.info("\n🧩 Testing Optional Bot Modules (may be missing)...")
    optional_modules_passed = 0
    for module in OPTIONAL_MODULES:
        if test_import(module, critical=False):
            optional_modules_passed += 1
    
    logger.info(f"Optional Modules: {optional_modules_passed}/{len(OPTIONAL_MODULES)} available")
    
    # Summary
    logger.info("\n" + "=" * 60)
    if all_passed:
        logger.info("✅ ALL CRITICAL IMPORTS PASSED")
        logger.info("=" * 60)
        sys.exit(0)
    else:
        logger.error("❌ SOME CRITICAL IMPORTS FAILED")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()