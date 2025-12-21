from macro_bubble_detector import MacroBubbleDetector
from cds_analyzer import CDSAnalyzer
from structured_product_analyzer import StructuredProductAnalyzer

class GreatestTradeAgent:
    def __init__(self, execution_hook=None):
        self.macro = MacroBubbleDetector()
        self.cds = CDSAnalyzer()
        self.struct = StructuredProductAnalyzer()
        self.execution_hook = execution_hook

    def run_full_analysis(self):
        macro_res = self.macro.analyze()
        cds_res = self.cds.analyze_cds("AAA", 50)
        struct_res = self.struct.analyze_tranches(0.05, [
            {"name": "Equity", "attach_pct": 0, "detach_pct": 5},
            {"name": "Mezz", "attach_pct": 5, "detach_pct": 20},
            {"name": "Senior", "attach_pct": 20, "detach_pct": 100},
        ])
        signal = {"macro": macro_res, "cds": cds_res, "struct": struct_res}
        if macro_res["bubble_flag"] and cds_res["verdict"] == "underpriced":
            action = {"trade": "BUY_CDS"}
            signal["recommended_action"] = action
            if self.execution_hook: self.execution_hook(action)
        return signal
