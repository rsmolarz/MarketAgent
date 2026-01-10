import json
import time
import importlib
from pathlib import Path
from typing import Callable, Any, Dict, List

from telemetry.logger import log_event, new_run_id
from telemetry.reward import reward as compute_reward

def load_callable(module_path: str, callable_name: str) -> Callable:
    mod = importlib.import_module(module_path)
    if "." in callable_name:
        class_name, method_name = callable_name.split(".")
        cls = getattr(mod, class_name)
        instance = cls()
        return getattr(instance, method_name)
    return getattr(mod, callable_name)

def load_adapter(adapter_spec: str) -> Callable:
    module_path, func_name = adapter_spec.split(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, func_name)

def validate_schema(output: Any, schema: Dict) -> bool:
    if schema is None:
        return True
    
    schema_type = schema.get("type")
    
    if schema_type == "list":
        if not isinstance(output, list):
            return False
        item_schema = schema.get("item")
        if item_schema:
            for item in output:
                if not validate_schema(item, item_schema):
                    return False
        return True
    
    elif schema_type == "dict":
        if not isinstance(output, dict):
            return False
        required_keys = schema.get("required_keys", [])
        for key in required_keys:
            if key not in output:
                return False
        return True
    
    return True

def run_suite(module: str, callable_name: str, suite_path: str, out_path: str, 
              eval_adapter: str = None):
    suite_file = Path(suite_path)
    
    if not suite_file.exists():
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_text(json.dumps({
            "module": module,
            "callable": callable_name,
            "suite": suite_path,
            "error": "Suite file not found",
            "results": []
        }, indent=2))
        return []
    
    if eval_adapter:
        fn = load_adapter(eval_adapter)
    else:
        fn = load_callable(module, callable_name)
    
    suite = suite_file.read_text().splitlines()
    results = []

    for line in suite:
        if not line.strip():
            continue
        case = json.loads(line)
        run_id = new_run_id()
        t0 = time.time()
        try:
            input_data = case.get("input", {})
            if isinstance(input_data, dict):
                output = fn(input_data) if eval_adapter else fn(**input_data)
            else:
                output = fn(input_data)
            
            schema = case.get("schema")
            schema_valid = validate_schema(output, schema)
            
            ok = schema_valid
            err = None if schema_valid else "Schema validation failed"
        except Exception as e:
            output = None
            ok = False
            err = str(e)

        lat_ms = int((time.time() - t0) * 1000)
        
        event = {
            "agent": module,
            "latency_ms": lat_ms,
            "cost_usd": None,
        }
        r = compute_reward(event, output)
        
        log_event(
            agent=module,
            run_id=run_id,
            latency_ms=lat_ms,
            cost_usd=None,
            error=err,
            reward=r,
        )

        results.append({
            "id": case.get("id"),
            "ok": ok,
            "latency_s": round(lat_ms / 1000, 4),
            "output": output,
            "error": err,
            "reward": r
        })

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(json.dumps({
        "module": module,
        "callable": callable_name,
        "suite": suite_path,
        "results": results
    }, indent=2))

    return results

def run_suite_from_manifest(agent_config: Dict) -> List[Dict]:
    return run_suite(
        module=agent_config["module"],
        callable_name=agent_config["callable"],
        suite_path=agent_config["eval_suite"],
        out_path=f"eval/results/{agent_config['name']}.json",
        eval_adapter=agent_config.get("eval_adapter")
    )
