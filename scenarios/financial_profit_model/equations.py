"""
企业商业财务利润连续核算方程组 (Financial Equations).
涵盖营业收入、可变成本、毛利、EBITDA、EBIT、利润总额与净利润。
"""

def calc_revenue_wanke(price_cny: float, volume: float) -> float:
    """营业收入 (万元)"""
    return (price_cny * volume) / 10000.0


def calc_variable_cost_total_wanke(unit_cost_cny: float, volume: float) -> float:
    """可变成本总额 (万元)"""
    return (unit_cost_cny * volume) / 10000.0


def calc_gross_profit_wanke(revenue_wanke: float, variable_cost_wanke: float) -> float:
    """毛利润 (万元)"""
    return revenue_wanke - variable_cost_wanke


def calc_ebitda_wanke(gross_profit_wanke: float, fixed_costs_wanke: float) -> float:
    """息税折旧摊销前利润 (EBITDA, 万元)"""
    return gross_profit_wanke - fixed_costs_wanke


def calc_ebit_wanke(ebitda_wanke: float, depreciation_wanke: float) -> float:
    """息税前利润 (EBIT, 万元)"""
    return ebitda_wanke - depreciation_wanke


def calc_ebt_wanke(ebit_wanke: float, interest_wanke: float) -> float:
    """利润总额 (EBT, 万元)"""
    return ebit_wanke - interest_wanke


def calc_net_profit_wanke(ebt_wanke: float, tax_rate: float = 0.25) -> float:
    """税后净利润 (万元)"""
    if ebt_wanke <= 0:
        return ebt_wanke  # 亏损不计所得税
    tax = ebt_wanke * tax_rate
    return ebt_wanke - tax
