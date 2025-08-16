
from setuptools import setup, find_packages

setup(
    name="market_inefficiency_agent",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "fastapi", "uvicorn", "ccxt", "requests", "pydantic",
        "plotly", "notifiers", "apscheduler", "pandas", "yfinance"
    ],
    entry_points={
        'console_scripts': [
            'market-agent = main:main'
        ]
    }
)
