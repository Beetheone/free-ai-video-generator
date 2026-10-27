"""Read-only model-catalog diagnosis after an ambiguous inference failure."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

import requests

from .core import Blocked, Model, provider_error, public_url, save


def probe_catalog():
    model = Model()
    if not model.key:
        raise Blocked("MODEL_CREDENTIAL_REQUIRED", "Model key is absent; no catalog request made")
    if not model.base or not model.name:
        raise Blocked("MODEL_CONFIG", "Choose a provider and model before catalog diagnosis")
    if urlsplit(model.base).hostname in {"models.github.ai","models.inference.ai.azure.com"}:
        raise Blocked("MODEL_PROVIDER_RETIRED", "GitHub Models is retired; no catalog request made")
    public_url(model.base)
    report = {"provider_hostname":urlsplit(model.base).hostname, "model":model.name,
              "operation":"GET models (read only)", "inference_tested":False,
              "notice":"Catalog access does not establish paid credit, quota, inference authorization or quality."}
    try:
        r = requests.get(model.base+"/models", headers={"Authorization":"Bearer "+model.key,"Accept":"application/json"},
                         timeout=(10,30), allow_redirects=False)
    except requests.RequestException as exc:
        return {**report,"status":"CATALOG_NETWORK_ERROR","error_type":type(exc).__name__}
    report.update(http_status=r.status_code, response_metadata=provider_error(r))
    if r.status_code != 200:
        return {**report,"status":"CATALOG_UNAVAILABLE"}
    try:
        body = r.json()
        data = body.get("data") if isinstance(body,dict) else None
        if not isinstance(data,list):
            raise ValueError
    except ValueError:
        return {**report,"status":"INVALID_CATALOG_RESPONSE"}
    report.update(status="CATALOG_ACCESSIBLE_INFERENCE_UNVERIFIED",
                  chosen_model_listed=any(isinstance(item,dict) and item.get("id")==model.name for item in data))
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description="Diagnose catalog access without generation or billing changes")
    p.add_argument("--after-failed-run",type=Path)
    p.add_argument("--out",type=Path,default=Path("output/model-diagnosis.json"))
    args = p.parse_args(argv)
    if args.after_failed_run:
        reports = [json.loads(path.read_text("utf-8")) for path in args.after_failed_run.glob("*/qa_report.json")]
        ambiguous = [r for r in reports if r.get("blocker",{}).get("code")=="MODEL_UNAVAILABLE"
                     and not any(code in r["blocker"].get("detail","") for code in ("insufficient_quota","invalid_api_key","rate_limit_exceeded","model_not_found"))]
        if not ambiguous:
            save(args.out,{"status":"NOT_NEEDED","notice":"No ambiguous provider failure; no catalog request made"})
            return 0
    try:
        report = probe_catalog()
    except Blocked as exc:
        report = {"status":"BLOCKED","blocker":{"code":exc.code,"detail":exc.detail}}
    save(args.out,report)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report["status"]=="CATALOG_ACCESSIBLE_INFERENCE_UNVERIFIED" else 2


if __name__=="__main__":
    raise SystemExit(main())
