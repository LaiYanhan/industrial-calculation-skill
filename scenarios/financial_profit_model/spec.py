"""
企业财务商业利润测算场景实现类 (Financial Profit Model Spec).
实现营收、成本、毛利、EBITDA、税金与净利润的闭环计算与反解。
"""

from typing import Any, Dict, List, Tuple
from scenarios.base import BaseScenarioSpec
from engine.fsm.context import ExecutionContext
import scenarios.financial_profit_model.equations as eq


class FinancialProfitModelSpec(BaseScenarioSpec):

    def __init__(self):
        super().__init__("financial_profit_model")
        self.alias_map = {
            "产品单价": "unit_price_cny",
            "销售单价": "unit_price_cny",
            "单价": "unit_price_cny",
            "售价": "unit_price_cny",
            "产品销量": "sales_volume",
            "销量": "sales_volume",
            "销售件数": "sales_volume",
            "单位可变成本": "variable_cost_per_unit_cny",
            "单件成本": "variable_cost_per_unit_cny",
            "固定运营成本": "fixed_operating_costs_wanke",
            "固定开支": "fixed_operating_costs_wanke",
            "折旧摊销": "depreciation_wanke",
            "利息支出": "interest_expenses_wanke",
            "企业所得税率": "corporate_tax_rate",
            "税率": "corporate_tax_rate",
        }
        self.required_params = [
            "unit_price_cny",
            "sales_volume",
        ]

    def lookup_references(self, canonical_params: Dict[str, float]) -> Dict[str, Any]:
        # 检索财务常数或基准税率
        tax_rate = canonical_params.get("corporate_tax_rate", 0.25)
        return {"effective_tax_rate": tax_rate}

    def solve_continuous(
        self,
        params: Dict[str, float],
        references: Dict[str, Any],
        mode: str = "FORWARD"
    ) -> Dict[str, float]:
        price = params.get("unit_price_cny", 100.0)
        volume = params.get("sales_volume", 10000.0)
        unit_cost = params.get("variable_cost_per_unit_cny", 50.0)
        fixed_cost = params.get("fixed_operating_costs_wanke", 200.0)
        depreciation = params.get("depreciation_wanke", 50.0)
        interest = params.get("interest_expenses_wanke", 20.0)
        tax_rate = references.get("effective_tax_rate", 0.25)

        revenue = eq.calc_revenue_wanke(price, volume)
        var_cost = eq.calc_variable_cost_total_wanke(unit_cost, volume)
        gross_profit = eq.calc_gross_profit_wanke(revenue, var_cost)
        ebitda = eq.calc_ebitda_wanke(gross_profit, fixed_cost)
        ebit = eq.calc_ebit_wanke(ebitda, depreciation)
        ebt = eq.calc_ebt_wanke(ebit, interest)
        net_profit = eq.calc_net_profit_wanke(ebt, tax_rate)

        return {
            "revenue_wanke": round(revenue, 2),
            "variable_cost_total_wanke": round(var_cost, 2),
            "gross_profit_wanke": round(gross_profit, 2),
            "ebitda_wanke": round(ebitda, 2),
            "ebit_wanke": round(ebit, 2),
            "ebt_wanke": round(ebt, 2),
            "net_profit_wanke": round(net_profit, 2),
        }

    def regularize_discrete(
        self,
        continuous_results: Dict[str, float],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        # 财务销量整件规整
        vol = params.get("sales_volume", 0.0)
        return {"discrete_sales_volume": int(vol)}

    def cascade_metrics(
        self,
        continuous_results: Dict[str, float],
        discrete_results: Dict[str, Any],
        params: Dict[str, float]
    ) -> Dict[str, Any]:
        revenue = continuous_results.get("revenue_wanke", 1.0)
        gross_profit = continuous_results.get("gross_profit_wanke", 0.0)
        net_profit = continuous_results.get("net_profit_wanke", 0.0)

        # 衍生比率指标
        gross_margin = (gross_profit / revenue) if revenue > 0 else 0.0
        net_margin = (net_profit / revenue) if revenue > 0 else 0.0

        return {
            "gross_margin_pct": round(gross_margin * 100, 2),
            "net_margin_pct": round(net_margin * 100, 2),
        }

    def audit_sanity(self, context: ExecutionContext) -> Tuple[List[str], List[str]]:
        violations = []
        warnings = []

        price = context.canonical_params.get("unit_price_cny", 0.0)
        cost = context.canonical_params.get("variable_cost_per_unit_cny", 0.0)

        if price <= 0:
            violations.append(f"产品单价 {price}元 非法，必须为正数")
        if cost > price:
            warnings.append(f"单位可变成本 {cost}元 高于产品售价 {price}元，存在严重毛利倒挂风险")

        return violations, warnings
