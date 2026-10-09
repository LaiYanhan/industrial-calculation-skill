"""
商业与财务基准指标适配器 (Financial Benchmark Adapter).
提供基准增值税率、企业所得税率、LPR贷款基准利率、折旧年限等。
"""

from typing import Dict


class FinancialBenchmarkAdapter:
    """商业与财务基准参数查询器"""

    BENCHMARK_RATES = {
        "vat_general_rate": 0.13,            # 增值税标准税率 13%
        "vat_service_rate": 0.06,            # 服务业增值税率 6%
        "corporate_income_tax_rate": 0.25,   # 企业所得税标准税率 25%
        "cit_high_tech_rate": 0.15,          # 高新技术企业所得税 15%
        "lpr_5year_rate": 0.0385,            # 5年期以上LPR基准利率 3.85%
        "standard_discount_rate": 0.08,      # 行业基准折现率 8%
    }

    @classmethod
    def get_benchmark_rate(cls, rate_key: str) -> float:
        return cls.BENCHMARK_RATES.get(rate_key, 0.0)

    @classmethod
    def get_all_benchmarks(cls) -> Dict[str, float]:
        return dict(cls.BENCHMARK_RATES)
